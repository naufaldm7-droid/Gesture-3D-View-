;;; TCI Gesture Control untuk AutoCAD
;;; Perintah GK / GESTURE / KAMERA = nyalakan atau matikan kendali gestur tangan (kamera laptop).
;;; Dimuat otomatis oleh AutoCAD dari ...\ApplicationPlugins\TCIGestureControl.bundle (PackageContents.xml).
;;; Memanggil GestureControl.exe yang sama dua kali = mematikannya (program hanya berjalan satu salinan).

(defun tci-gc-exe (/ p c)
  (foreach r (list (getenv "APPDATA") (getenv "ProgramData") (getenv "ProgramFiles"))
    (if (and r (not p))
      (progn
        (setq c (strcat r "\\Autodesk\\ApplicationPlugins\\TCIGestureControl.bundle\\Contents\\app\\GestureControl.exe"))
        (if (findfile c) (setq p c))
      )
    )
  )
  p
)

(defun tci-gc-toggle (/ exe)
  (setq exe (tci-gc-exe))
  (if exe
    (progn
      (startapp (strcat "\"" exe "\""))
      (princ "\nGesture Control: nyala/mati (ketik lagi untuk mematikan).")
    )
    (princ "\nGesture Control: GestureControl.exe tidak ditemukan - pasang ulang plugin (INSTAL.bat).")
  )
  (princ)
)

(defun c:GK () (tci-gc-toggle))
(defun c:GESTURE () (tci-gc-toggle))
(defun c:KAMERA () (tci-gc-toggle))

(princ "\nTCI Gesture Control siap: ketik GK untuk menyalakan/mematikan kamera gestur.")
(princ)
