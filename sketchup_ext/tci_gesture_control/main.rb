# TCI Gesture Control untuk SketchUp — jembatan antara aplikasi gestur (Python) dan SketchUp.
#
# - Server TCP lokal (127.0.0.1 saja) yang menerima operasi dari DAFTAR PUTIH: hello, action (nama aksi
#   Sketchup.send_action yang divalidasi), render, xray, camera. Tidak ada eksekusi kode bebas.
# - Kamera digerakkan langsung (orbit mengelilingi target, pan, zoom) supaya gestur dua tangan halus.
# - Perintah "Gesture Control (nyala/mati)" di menu Extensions + toolbar: menyalakan/mematikan aplikasi
#   gestur (peluncur yang sama dipanggil dua kali = mati). Bisa diberi shortcut di Preferences > Shortcuts.

require 'sketchup.rb'
require 'socket'
require 'json'

module TCI
  module GestureControl
    PORT = 47820
    ACTION_RE = /\A[A-Za-z0-9]+:\z/
    POLE_GUARD = 2.0.degrees # jangan orbit melewati kutub (kamera terbalik)

    @server = nil
    @clients = []
    @timer = nil

    def self.app_dir
      APP_DIR # diisi oleh pemasang (tci_gesture_control.rb)
    end

    # ------------------------------------------------------------------ server
    def self.start_server
      return if @server
      @server = TCPServer.new('127.0.0.1', PORT)
      @timer = UI.start_timer(0.02, true) { poll }
      puts "[Gesture Control] jembatan siap di 127.0.0.1:#{PORT}"
    rescue StandardError => e
      @server = nil
      puts "[Gesture Control] jembatan gagal dibuka: #{e.class}: #{e.message}"
    end

    def self.poll
      return unless @server
      socks = [@server] + @clients.map { |c| c[:sock] }
      ready = IO.select(socks, nil, nil, 0)
      return unless ready
      ready[0].each do |s|
        if s == @server
          begin
            @clients << { sock: @server.accept, buf: String.new }
          rescue StandardError
            nil
          end
          next
        end
        cl = @clients.find { |c| c[:sock] == s }
        next unless cl
        begin
          data = s.readpartial(65_536)
          cl[:buf] << data
        rescue EOFError, IOError, SystemCallError
          drop(cl)
          next
        end
        while (i = cl[:buf].index("\n"))
          line = cl[:buf].slice!(0..i)
          reply = handle(line)
          next unless reply
          begin
            s.write(reply.to_json + "\n")
          rescue StandardError
            drop(cl)
            break
          end
        end
      end
    rescue StandardError => e
      puts "[Gesture Control] #{e.class}: #{e.message}"
    end

    def self.drop(cl)
      begin
        cl[:sock].close
      rescue StandardError
        nil
      end
      @clients.delete(cl)
    end

    # ------------------------------------------------------------------ operasi
    def self.handle(line)
      msg = JSON.parse(line)
      id = msg['id']
      res =
        case msg['op']
        when 'hello'
          { ok: true, sketchup: Sketchup.version, port: PORT }
        when 'action'
          name = msg['arg'].to_s
          if name =~ ACTION_RE
            { ok: Sketchup.send_action(name) ? true : false }
          else
            { ok: false, error: "nama aksi tidak sah: #{name}" }
          end
        when 'render'
          Sketchup.active_model.rendering_options['RenderMode'] = Integer(msg['arg'])
          { ok: true }
        when 'xray'
          ro = Sketchup.active_model.rendering_options
          ro['ModelTransparency'] = !ro['ModelTransparency']
          { ok: true }
        when 'camera'
          camera_step(msg)
          { ok: true }
        else
          { ok: false, error: "operasi tidak dikenal: #{msg['op']}" }
        end
      return nil unless id || res[:ok] == false # gerak kamera rutin tidak dijawab (hemat lalu lintas)
      res[:id] = id if id
      res
    rescue StandardError => e
      { ok: false, error: "#{e.class}: #{e.message}" }
    end

    # Gerak kamera dari dua tangan. dx/dy = geser titik tengah tangan (lebar frame kamera, y ke bawah),
    # turn = putaran "setir" (radian, + searah jarum jam di layar), zoom = perubahan log rentang tangan.
    def self.camera_step(m)
      view = Sketchup.active_model.active_view
      cam = view.camera
      eye = cam.eye
      target = cam.target
      up = cam.up
      sx = m['invert_x'] ? -1.0 : 1.0
      sy = m['invert_y'] ? -1.0 : 1.0
      dx = m['dx'].to_f * sx
      dy = m['dy'].to_f * sy
      if m['kind'] == 'orbit'
        g = m['orbit_gain'].to_f
        yaw = -(dx * g) - m['turn'].to_f
        pitch = -(dy * g)
        if yaw.abs > 1e-6
          t = Geom::Transformation.rotation(target, Z_AXIS, yaw)
          eye = eye.transform(t)
          up = up.transform(t)
        end
        if pitch.abs > 1e-6
          dir = target - eye
          right = dir * up
          if right.length > 1e-9
            t = Geom::Transformation.rotation(target, right, pitch)
            new_eye = eye.transform(t)
            off = new_eye - target
            if off.angle_between(Z_AXIS) > POLE_GUARD && off.angle_between(Z_AXIS.reverse) > POLE_GUARD
              eye = new_eye
              up = up.transform(t)
            end
          end
        end
      else # pan: tangan ke kanan -> model ikut ke kanan (kamera ke kiri); tangan naik -> model naik
        dir = target - eye
        right = unit(dir * up) # Vector3d#* = perkalian silang
        upn = unit(up)
        k = m['pan_gain'].to_f * (cam.perspective? ? dir.length : cam.height)
        move = scaled(right, -dx * k) + scaled(upn, dy * k)
        eye = eye.offset(move)
        target = target.offset(move)
      end
      z = m['zoom'].to_f * m['zoom_gain'].to_f
      if z.abs > 1e-6
        f = Math.exp(z) # rentangkan tangan (z > 0) = zoom in
        if cam.perspective?
          off = eye - target
          off.length = [off.length / f, 1.0e-3].max
          eye = target.offset(off)
        else
          cam.height = cam.height / f
        end
      end
      cam.set(eye, target, up)
      view.invalidate
    end

    def self.unit(v)
      n = v.length
      n > 1e-12 ? Geom::Vector3d.new(v.x / n, v.y / n, v.z / n) : Geom::Vector3d.new(0, 0, 0)
    end

    def self.scaled(v, s)
      Geom::Vector3d.new(v.x * s, v.y * s, v.z * s)
    end

    # ------------------------------------------------------------------ nyala/mati aplikasi
    def self.toggle_app
      dir = app_dir
      pyw = File.join(dir, '.venv', 'Scripts', 'pythonw.exe')
      launcher = File.join(dir, 'gesture_cad_start.pyw')
      cfg = File.join(dir, 'config_sketchup.json')
      missing = [pyw, launcher, cfg].reject { |p| File.exist?(p) }
      unless missing.empty?
        UI.messagebox("Gesture Control belum lengkap terpasang:\n#{missing.join("\n")}\n\n" \
                      "Jalankan ulang pemasang di folder aplikasi.")
        return
      end
      pid = Process.spawn(pyw, launcher, '--config', cfg, chdir: dir)
      Process.detach(pid)
    rescue StandardError => e
      UI.messagebox("Gesture Control gagal dijalankan: #{e.message}")
    end

    unless file_loaded?(__FILE__)
      start_server
      cmd = UI::Command.new('Gesture Control (nyala/mati)') { toggle_app }
      icons = File.join(__dir__, 'icons')
      if File.exist?(File.join(icons, 'hand_24.png'))
        cmd.small_icon = File.join(icons, 'hand_24.png')
        cmd.large_icon = File.join(icons, 'hand_32.png')
      end
      cmd.tooltip = 'Gesture Control'
      cmd.status_bar_text = 'Nyalakan / matikan kendali gestur tangan lewat kamera laptop'
      UI.menu('Extensions').add_item(cmd)
      tb = UI::Toolbar.new('Gesture Control')
      tb.add_item(cmd)
      tb.restore
      file_loaded(__FILE__)
    end
  end
end
