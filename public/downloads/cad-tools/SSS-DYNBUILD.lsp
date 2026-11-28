;;; SSS-DYNBUILD.lsp  ·  SoCal Super Standards dynamic block families
;;;
;;; Builds every family in SSS-DYNBUILD-MANIFEST.csv (unzipped from SSS-DYNBUILD.zip) as one dynamic
;;; block: one visibility state per published variant, a rotation parameter and flip X and flip Y
;;; parameters, all at the shared base point (0,0), each with its action on every state's geometry.
;;; Geometry stays on layer 0, color, linetype and lineweight ByLayer; NOPLOT frames stay on NOPLOT.
;;;
;;;   SSSDYNTEST   builds the first family only (a quick check), into OUT\ beside the manifest
;;;   SSSDYNBUILD  builds every family, one DWG each, into OUT\ beside the manifest
;;;
;;; Start in a new drawing (feet). The routine logs each step to OUT\SSS-DYNBUILD.log. If a command
;;; stops with a prompt the routine did not expect, send the log: prompts differ between releases.

(vl-load-com)

(defun sss:split (s sep / out i)
  (setq out '())
  (while (setq i (vl-string-search sep s))
    (setq out (cons (substr s 1 i) out) s (substr s (+ i 1 (strlen sep)))))
  (reverse (cons s out)))

(defun sss:csv-line (s / out cur q i ch)
  (setq out '() cur "" q nil i 1)
  (while (<= i (strlen s))
    (setq ch (substr s i 1))
    (cond ((and q (= ch "\"") (= (substr s (1+ i) 1) "\"")) (setq cur (strcat cur "\"") i (1+ i)))
          ((= ch "\"") (setq q (not q)))
          ((and (not q) (= ch ",")) (setq out (cons cur out) cur ""))
          (t (setq cur (strcat cur ch))))
    (setq i (1+ i)))
  (reverse (cons cur out)))

(defun sss:read-manifest (csv / f line rows fams fam)
  (setq f (open csv "r") rows '())
  (read-line f)                                        ; header
  (while (setq line (read-line f))
    (if (> (strlen line) 3) (setq rows (cons (sss:csv-line line) rows))))
  (close f)
  (foreach r (reverse rows)                            ; (family state file label)
    (if (setq fam (assoc (car r) fams))
      (setq fams (subst (append fam (list (cdr r))) fam fams))
      (setq fams (append fams (list (list (car r) (cdr r)))))))
  fams)

(defun sss:log (msg)
  (princ (strcat "\nSSS: " msg))
  (if *sss-log* (progn (write-line msg *sss-log*))))

(defun sss:new-ents (after / out e)
  (setq out (ssadd) e (if after (entnext after) (entnext)))
  (while e (ssadd e out) (setq e (entnext e)))
  out)

(defun sss:layer (name / )
  (if (not (tblsearch "LAYER" name)) (command "_.-LAYER" "_N" name ""))
  name)

(defun sss:place-state (dir file tag / before ss i e typ)
  ;; insert the state drawing exploded once, explode its block once more, drop the code label
  (setq before (entlast))
  (command "_.-INSERT" (strcat "*" dir "\\" file) "0,0" "1" "0")
  (setq ss (sss:new-ents before) i 0)
  (repeat (sslength ss)
    (setq e (ssname ss i) typ (cdr (assoc 0 (entget e))))
    (cond ((member typ '("MTEXT" "TEXT")) (entdel e))
          ((= typ "INSERT") (command "_.EXPLODE" e)))
    (setq i (1+ i)))
  (setq ss (sss:new-ents before) i 0)
  (repeat (sslength ss)                                ; tag this state's geometry by a temporary layer
    (setq e (ssname ss i))
    (if (entget e)
      (progn
        (setq ed (entget e))
        (setq ed (subst (cons 8 (if (= (cdr (assoc 8 ed)) "NOPLOT") (strcat tag "$NP") tag)) (assoc 8 ed) ed))
        (entmod ed)))
    (setq i (1+ i)))
  ss)

(defun sss:by-layer (lay)
  (ssget "_X" (list (cons 8 lay))))

(defun sss:build-family (fam dir out / name states n all tag lays sizeprm r)
  (setq name (car fam) states (cdr fam) n 0 lays '())
  (sss:log (strcat "family " name " (" (itoa (length states)) " states)"))
  (command "_.ERASE" "_ALL" "")
  (foreach s states                                    ; s = (state file label)
    (setq n (1+ n) tag (sss:layer (strcat "SSS$STATE$" (itoa n))))
    (sss:layer (strcat tag "$NP"))
    (sss:place-state dir (cadr s) tag)
    (setq lays (append lays (list (list (car s) tag)))))
  (setq all (ssget "_X" '((410 . "Model"))))
  (if (tblsearch "BLOCK" name)
    (command "_.-BLOCK" name "_Y" "0,0" all "")
    (command "_.-BLOCK" name "0,0" all ""))
  ;; block editor: visibility states, rotation and flips at the base point
  (command "_.BEDIT" name)
  (setq r 2.0)
  (command "_.BPARAMETER" "_Visibility" (list 0.0 (- r)) "1")
  (foreach l lays
    (command "_.-BVSTATE" "_New" (car l) "_Hide")
    (if (setq ss (sss:by-layer (cadr l))) (command "_.BVSHOW" ss "" "_Current"))
    (if (setq ss (sss:by-layer (strcat (cadr l) "$NP"))) (command "_.BVSHOW" ss "" "_Current")))
  (command "_.-BVSTATE" "_Set" (car (car lays)))
  (command "_.-BVSTATE" "_Delete" "VisibilityState0")
  (setq all (ssget "_X" '((0 . "~ACDB*"))))
  (command "_.BPARAMETER" "_Rotation" "0,0" (list r 0.0) "0" (list (* 1.4 r) (* 1.4 r)))
  (command "_.BACTIONTOOL" "_Rotate" (list r 0.0) all "")
  (command "_.BPARAMETER" "_Flip" "0,0" (list 0.0 r) (list (- r) (* 1.6 r)))
  (command "_.BACTIONTOOL" "_Flip" (list 0.0 (* 0.5 r)) all "")
  (command "_.BPARAMETER" "_Flip" "0,0" (list r 0.0) (list (* 1.6 r) (- r)))
  (command "_.BACTIONTOOL" "_Flip" (list (* 0.5 r) 0.0) all "")
  (foreach l lays                                      ; states back to layer 0 / NOPLOT
    (if (setq ss (sss:by-layer (cadr l))) (command "_.CHPROP" ss "" "_LA" "0" ""))
    (if (setq ss (sss:by-layer (strcat (cadr l) "$NP"))) (command "_.CHPROP" ss "" "_LA" "NOPLOT" "")))
  (command "_.BSAVE")
  (command "_.BCLOSE")
  (command "_.-WBLOCK" (strcat out "\\" name ".dwg") name)
  (command "_.-PURGE" "_LA" "SSS$STATE$*" "_N")
  (sss:log (strcat "  wrote " out "\\" name ".dwg")))

(defun sss:run (limit / csv dir out fams old n)
  (setq csv (getfiled "SSS dynamic family manifest" "" "csv" 0))
  (if (null csv) (exit))
  (setq dir (vl-filename-directory csv) out (strcat dir "\\OUT"))
  (vl-mkdir out)
  (setq *sss-log* (open (strcat out "\\SSS-DYNBUILD.log") "w"))
  (setq old (mapcar 'getvar '("CMDECHO" "FILEDIA" "CMDDIA" "EXPERT" "ATTREQ" "INSUNITS" "CLAYER")))
  (mapcar 'setvar '("CMDECHO" "FILEDIA" "CMDDIA" "EXPERT" "ATTREQ" "INSUNITS") '(1 0 0 5 0 2))
  (sss:layer "NOPLOT")
  (command "_.-LAYER" "_P" "_N" "NOPLOT" "")
  (setvar "CLAYER" "0")
  (setq fams (sss:read-manifest csv) n 0)
  (foreach fam fams
    (if (or (null limit) (< n limit))
      (progn (sss:build-family fam dir out) (setq n (1+ n)))))
  (mapcar 'setvar '("CMDECHO" "FILEDIA" "CMDDIA" "EXPERT" "ATTREQ" "INSUNITS" "CLAYER") old)
  (sss:log (strcat (itoa n) " families written to " out))
  (close *sss-log*)
  (setq *sss-log* nil)
  (princ))

(defun c:SSSDYNTEST () (sss:run 1))
(defun c:SSSDYNBUILD () (sss:run nil))

(princ "\nSSS-DYNBUILD loaded. SSSDYNTEST builds one family as a check; SSSDYNBUILD builds them all.")
(princ)
