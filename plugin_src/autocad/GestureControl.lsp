;;; Gesture Control untuk AutoCAD
;;; Perintah GK / GESTURE / KAMERA = nyalakan atau matikan kendali gestur tangan (kamera laptop).
;;; Dimuat otomatis oleh AutoCAD dari ...\ApplicationPlugins\GestureControl.bundle (PackageContents.xml).
;;; Memanggil GestureControl.exe yang sama dua kali = mematikannya (program hanya berjalan satu salinan).

(defun gc-exe (/ p c)
  (foreach r (list (getenv "APPDATA") (getenv "ProgramData") (getenv "ProgramFiles"))
    (if (and r (not p))
      (progn
        (setq c (strcat r "\\Autodesk\\ApplicationPlugins\\GestureControl.bundle\\Contents\\app\\GestureControl.exe"))
        (if (findfile c) (setq p c))
      )
    )
  )
  p
)

(defun gc-toggle (/ exe)
  (setq exe (gc-exe))
  (if exe
    (progn
      (startapp (strcat "\"" exe "\""))
      (princ "\nGesture Control: nyala/mati (ketik lagi untuk mematikan).")
    )
    (princ "\nGesture Control: GestureControl.exe tidak ditemukan - pasang ulang plugin (INSTAL.bat).")
  )
  (princ)
)

(defun c:GK () (gc-toggle))
(defun c:GESTURE () (gc-toggle))
(defun c:KAMERA () (gc-toggle))

(princ "\nGesture Control siap: ketik GK untuk menyalakan/mematikan kamera gestur.")
(princ)
