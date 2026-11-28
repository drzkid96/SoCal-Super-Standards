;;; SSS-DYNBUILD.lsp  ·  SoCal Super Standards dynamic block builder (v5)
;;;
;;; Open SSS-DYNAMIC-SOURCE.dwg, APPLOAD this file, then run:
;;;   SSSDYNTEST    builds four samples (turn arrow, continental crosswalk, green bike crossing, a signal head)
;;;   SSSDYNBUILD   builds every family listed in the drawing
;;;   SSSDYNONE     builds one family by name
;;; Save the drawing and send it back. Each run writes SSS-DYNBUILD.log beside the drawing with a
;;; PASS or FAIL line per family; send the log too if anything fails.
;;;
;;; What each family gets (all about the base point at 0,0):
;;;   - Visibility, a short list: markings PROPOSED / EXISTING / REMOVE (LADOT Drafting Standards p. 10:
;;;     filled, outline, dashed outline; green paint has no REMOVE); signs their directions; Caltrans
;;;     signal symbols PROPOSED / EXISTING. A block with one state gets no list.
;;;   - Rotation grip at the base point; it also turns the length, width and flip grips.
;;;   - Crosswalks and the green bike crossing: a length grip repeats the bars or dashes; full-length
;;;     lines stretch; the bike crossing also has a width grip (5 to 8 ft lanes).
;;;   - Turn, through-turn and lane drop arrows: a flip grip about the lane center (x = 5.5 ft).
;;;   - The block description names the standard it comes from (Properties, Insert dialog).
;;; Variants stay nested blocks (never exploded); geometry stays on layer 0 ByLayer.

(vl-load-com)

;; ---------------------------------------------------------------- utilities
(defun sss:log (msg)
  (princ (strcat "\nSSS: " msg))
  (if *sss-log* (write-line msg *sss-log*))
  msg)

(defun sss:finish (/ n)
  ;; answer any prompt a release adds (grip counts, action locations) with its default
  (setq n 0)
  (while (and (> (getvar "CMDACTIVE") 0) (< n 12))
    (command "")
    (setq n (1+ n)))
  n)

(defun sss:cmd (args / r n)
  (setq r (vl-catch-all-apply 'vl-cmdf args))
  (setq n (sss:finish))
  (cond ((vl-catch-all-error-p r)
         (sss:log (strcat "    error in " (vl-princ-to-string (car args)) ": " (vl-catch-all-error-message r)))
         nil)
        ((not r) (sss:log (strcat "    " (vl-princ-to-string (car args)) " was refused")) nil)
        (t (if (> n 0) (sss:log (strcat "    " (car args) ": " (itoa n) " extra prompt(s) took the default")))
           t)))

(defun sss:layer (name)
  (if (not (tblsearch "LAYER" name))
    (entmake (list '(0 . "LAYER") '(100 . "AcDbSymbolTableRecord") '(100 . "AcDbLayerTableRecord")
                   (cons 2 name) '(70 . 0) '(62 . 7) '(6 . "Continuous"))))
  name)

(defun sss:wild (s)
  ;; escape wildcard characters for a selection filter
  (vl-list->string
    (apply 'append (mapcar '(lambda (c) (if (member c '(35 64 46 42 63 126 91 93 96 44)) (list 96 c) (list c)))
                           (vl-string->list s)))))

(defun sss:sel (flt / ss)
  ;; objects in the current space (the Block Editor included) matching a filter
  (cond ((setq ss (ssget "_A" flt)) ss)
        ((setq ss (ssget "_X" flt)) ss)
        (t nil)))

(defun sss:ss+ (a b / i)
  (cond ((null a) b) ((null b) a)
        (t (setq i 0) (repeat (sslength b) (ssadd (ssname b i) a) (setq i (1+ i))) a)))

;; the parameter a BPARAMETER call just made: the new Block Editor object whose type names a parameter.
;; Block Editor objects live inside the block, so the search uses the editor's own space ("_A"), not "_X".
(defun sss:ents (/ ss i out)
  (setq out '())
  (if (setq ss (ssget "_A"))
    (progn (setq i 0) (repeat (sslength ss) (setq out (cons (ssname ss i) out) i (1+ i)))))
  out)

(defun sss:param (before / found)
  (foreach e (sss:ents)
    (if (and (not (member e before)) (wcmatch (strcase (cdr (assoc 0 (entget e)))) "*PARAMETER*"))
      (setq found e)))
  (if (null found) (sss:log "    WARN parameter not found after BPARAMETER"))
  found)

(defun sss:make-param (args / before)
  (setq before (sss:ents))
  (sss:cmd args)
  (sss:param before))

;; one build step: an error is logged and the build goes on, so the block is always saved
(defun sss:step (label fn / r)
  (setq r (vl-catch-all-apply fn nil))
  (if (vl-catch-all-error-p r)
    (progn (sss:log (strcat "    STEP " label " stopped: " (vl-catch-all-error-message r))) (sss:finish) nil)
    r))

;; ---------------------------------------------------------------- family list
(defun sss:dict ()
  (cdr (assoc -1 (dictsearch (namedobjdict) "SSS_DYNAMIC"))))

(defun sss:read (d key / x out st)
  ;; one family XRECORD -> assoc list; states as (name block lines spacing)
  (if (setq x (dictsearch d key))
    (progn
      (foreach g x
        (cond ((= (car g) 300) (if st (setq out (cons (cons 'state (reverse st)) out))) (setq st (list (cdr g))))
              ((and st (member (car g) '(3 4 42))) (setq st (cons (cdr g) st)))
              ((member (car g) '(1 2 70 40 71 10 11 41 72 12 73 13 301)) (setq out (cons g out)))))
      (if st (setq out (cons (cons 'state (reverse st)) out)))
      (reverse out))))

(defun sss:families (/ d i key out f)
  (if (null (setq d (sss:dict))) (progn (sss:log "No SSS_DYNAMIC list: open SSS-DYNAMIC-SOURCE.dwg first.") nil)
    (progn
      (setq i 0)
      (while (setq f (sss:read d (setq key (strcat "F" (substr (itoa (+ 1000 i)) 2)))))
        (setq out (cons f out) i (1+ i)))
      (reverse out))))

(defun sss:get (f k) (cdr (assoc k f)))
(defun sss:states (f / out) (foreach g f (if (eq (car g) 'state) (setq out (cons (cdr g) out)))) (reverse out))

;; ---------------------------------------------------------------- build one family
(defun sss:place (blk tag / e)
  (entmake (list '(0 . "INSERT") (cons 2 blk) (cons 8 tag) '(10 0.0 0.0 0.0) '(41 . 1.0) '(42 . 1.0) '(43 . 1.0) '(50 . 0.0)))
  (entlast))

(defun sss:explode-into (blk tag / e objs out)
  ;; full-length lines are exploded once so the stretch action can move their far ends
  (setq e (sss:place blk tag) out (ssadd))
  (setq objs (vl-catch-all-apply 'vlax-invoke (list (vlax-ename->vla-object e) 'Explode)))
  (entdel e)
  (if (not (vl-catch-all-error-p objs))
    (foreach o objs (vla-put-Layer o tag) (ssadd (vlax-vla-object->ename o) out)))
  out)

(defun sss:build (f / name states n r fx sp len axis made i tag st e ss all lin wid w rot flp vis
                    spacings ok slot scale obj props names allowed nvis want)
  (setq name (sss:get f 1) states (sss:states f) n (length states)
        r (sss:get f 40) len (sss:get f 12) axis (sss:get f 73) slot (sss:get f 11) scale (sss:get f 41))
  (sss:bclose-discard)                     ; never start a family inside the Block Editor
  (sss:log (strcat "family " name " (" (itoa n) " states)"))
  (setvar "INSUNITS" (sss:get f 70))
  ;; 1. place every state at the base point, each on its own temporary layer
  (setq made (ssadd) i 0)
  (foreach st states            ; st = (name block lines spacing)
    (setq i (1+ i) tag (sss:layer (strcat "SSS$STATE$" (itoa i))))
    (sss:layer (strcat tag "$L"))
    (sss:layer (strcat tag "$U"))
    (if (/= (cadr st) "")
      (if (= (sss:get f 72) 1)
        (sss:ss+ made (sss:explode-into (cadr st) (strcat tag "$U")))   ; array units: plain geometry
        (ssadd (sss:place (cadr st) tag) made)))
    (if (/= (caddr st) "") (sss:ss+ made (sss:explode-into (caddr st) (strcat tag "$L")))))
  (if (= (sslength made) 0) (progn (sss:log "  FAIL nothing to place") (exit)))
  ;; 2. the block itself
  (if (tblsearch "BLOCK" name)
    (sss:cmd (list "_.-BLOCK" name "_Y" "0,0" made ""))
    (sss:cmd (list "_.-BLOCK" name "0,0" made "")))
  (if (not (tblsearch "BLOCK" name)) (progn (sss:log "  FAIL block was not created") (exit)))
  ;; 3. parameters and actions in the Block Editor
  (sss:cmd (list "_.-BEDIT" name))
  (if (/= (getvar "BLOCKEDITOR") 1) (progn (sss:log "  FAIL the Block Editor did not open") (exit)))
  (command "_.ZOOM" "_E")
  (setq all (sss:sel '((-4 . "<OR") (8 . "SSS$STATE$*") (-4 . "OR>"))))
  ;; length grip and arrays (crosswalks, bike crossings)
  (if (= (sss:get f 72) 1)
    (sss:step "length" '(lambda ()
      (setq lin (sss:make-param (list "_.BPARAMETER" "_Linear" '(0.0 0.0 0.0) len
                     (if (= axis 0) (list (/ (car len) 2.0) (- (* 2.0 r)) 0.0) (list (- (* 2.0 r)) (/ (cadr len) 2.0) 0.0))
                     "1")))
      (setq sp 0.0)
      (foreach st states (if (> (cadddr st) 0) (setq sp (cadddr st))))
      (if (and lin (> sp 0) (setq ss (sss:sel '((8 . "SSS$STATE$*$U")))))
        (sss:cmd (list "_.BACTIONTOOL" "_Array" lin ss "" (rtos sp 2 4))))
      (if (and lin (setq ss (sss:sel '((8 . "SSS$STATE$*$L")))))
        (sss:cmd (list "_.BACTIONTOOL" "_Stretch" lin ""
                       (if (= axis 0) (list (- (car len) 0.5) -2.0 0.0) (list -2.0 (- (cadr len) 0.5) 0.0))
                       (if (= axis 0) (list (+ (car len) 0.5) 14.0 0.0) (list 14.0 (+ (cadr len) 0.5) 0.0))
                       ss "")))
      ;; width grip (green bike crossing): stretches the dash and moves the far edge line
      (if (> (car (sss:get f 13)) 0)
        (progn
          (setq w (car (sss:get f 13)))
          (setq wid (sss:make-param (list "_.BPARAMETER" "_Linear" '(0.0 0.0 0.0) (list w 0.0 0.0) (list (/ w 2.0) (- (* 1.5 r)) 0.0) "1")))
          (if (and wid (setq ss (sss:sel '((8 . "SSS$STATE$*$U")))))
            (sss:cmd (list "_.BACTIONTOOL" "_Stretch" wid "" (list (- w 0.5) -1.0 0.0) (list (+ w 0.5) 3.0 0.0) ss "")))))
      t)))
  ;; flip about the lane center (lane arrows)
  (if (= (sss:get f 71) 1)
    (sss:step "flip" '(lambda ()
      (setq fx (car (sss:get f 10)))
      (setq flp (sss:make-param (list "_.BPARAMETER" "_Flip" (list fx 0.0 0.0) (list fx (* 2.0 r) 0.0) (list (+ fx r) (* 2.5 r) 0.0))))
      (if flp (sss:cmd (list "_.BACTIONTOOL" "_Flip" flp all "")))
      t)))
  ;; rotation about the base point: geometry plus the length and flip grips
  (sss:step "rotation" '(lambda ()
    (setq rot (sss:make-param (list "_.BPARAMETER" "_Rotation" '(0.0 0.0 0.0) (list r 0.0 0.0) "0" (list (* 1.4 r) (* 1.4 r) 0.0))))
    (setq ss (sss:ss+ (ssadd) all))
    (if lin (ssadd lin ss))
    (if wid (ssadd wid ss))
    (if flp (ssadd flp ss))
    (if rot (sss:cmd (list "_.BACTIONTOOL" "_Rotate" rot ss "")))
    t))
  ;; visibility last, so every grip shows in every state
  (if (> n 1)
    (sss:step "visibility" '(lambda ()
      (sss:cmd (list "_.BPARAMETER" "_Visibility" (list 0.0 (- (* 1.5 r)) 0.0) "1"))
      (setq i 0)
      (foreach st states
        (setq i (1+ i) tag (strcat "SSS$STATE$" (itoa i)))
        (sss:cmd (list "_.-BVSTATE" "_New" (car st) "_Hide"))
        (setq ss (sss:state-set tag))
        (foreach p (list lin wid flp rot) (if p (setq ss (if ss (ssadd p ss) (ssadd p)))))
        (if ss (sss:cmd (list "_.BVSHOW" ss "" "_Current"))
          (sss:log (strcat "  WARN state " (car st) " has no objects"))))
      (sss:cmd (list "_.-BVSTATE" "_Set" (car (car states))))
      (sss:cmd (list "_.-BVSTATE" "_Delete" "VisibilityState0"))
      t)))
  ;; temporary layers back to 0
  (if (setq ss (sss:sel '((8 . "SSS$STATE$*")))) (sss:cmd (list "_.CHPROP" ss "" "_LA" "0" "")))
  (sss:cmd (list "_.BSAVE"))
  (sss:cmd (list "_.BCLOSE"))
  (if (= (getvar "BLOCKEDITOR") 1) (progn (sss:bclose-discard) (sss:log "  FAIL the Block Editor would not close") (exit)))
  (vl-catch-all-apply 'vla-put-Comments
    (list (vla-item (vla-get-Blocks (vla-get-ActiveDocument (vlax-get-acad-object))) name) (sss:get f 301)))
  ;; 4. self-check on an inserted copy at the review slot
  (setq obj (vl-catch-all-apply 'vla-InsertBlock
              (list (vla-get-ModelSpace (vla-get-ActiveDocument (vlax-get-acad-object)))
                    (vlax-3d-point slot) name scale scale scale 0.0)))
  (if (vl-catch-all-error-p obj)
    (sss:log (strcat "  FAIL could not insert " name))
    (progn
      (setq props (vlax-invoke obj 'GetDynamicBlockProperties) names '() nvis 0)
      (foreach p props
        (setq names (cons (vla-get-PropertyName p) names))
        (if (wcmatch (strcase (vla-get-PropertyName p)) "VISIBILITY*")
          (setq allowed (vlax-get p 'AllowedValues) nvis (length allowed))))
      (setq want (list (if (> n 1) (= nvis n) t)
                       (vl-some '(lambda (s) (wcmatch (strcase s) "ANGLE*")) names)
                       (if (= (sss:get f 72) 1) (vl-some '(lambda (s) (wcmatch (strcase s) "DISTANCE*")) names) t)
                       (if (> (car (sss:get f 13)) 0)
                         (> (length (vl-remove-if-not '(lambda (s) (wcmatch (strcase s) "DISTANCE*")) names)) 1) t)
                       (if (= (sss:get f 71) 1) (vl-some '(lambda (s) (wcmatch (strcase s) "FLIP*")) names) t)))
      (sss:log (strcat (if (vl-every 'eval want) "  PASS " "  FAIL ") name
                       "  visibility " (itoa nvis) "/" (itoa (if (> n 1) n 0))
                       "  properties: " (sss:join (reverse names) ", ")))))
  (sss:cmd (list "_.-PURGE" "_LA" "SSS$STATE$*" "_N"))
  name)

(defun sss:state-set (tag)
  (sss:ss+ (sss:ss+ (sss:sel (list (cons 8 tag))) (sss:sel (list (cons 8 (strcat tag "$L")))))
           (sss:sel (list (cons 8 (strcat tag "$U"))))))

(defun sss:bclose-discard ()
  ;; leave the Block Editor without saving a half-built family
  (if (= (getvar "BLOCKEDITOR") 1)
    (progn (vl-catch-all-apply 'vl-cmdf '("_.BCLOSE"))
           (while (> (getvar "CMDACTIVE") 0) (command "_Discard")))))

(defun sss:join (lst sep / out)
  (setq out "")
  (foreach s lst (setq out (if (= out "") s (strcat out sep s))))
  out)

;; ---------------------------------------------------------------- run
(defun sss:run (pick / fams vars old done failed r)
  (setq *sss-log* (open (strcat (getvar "DWGPREFIX") "SSS-DYNBUILD.log") "a"))
  (sss:log (strcat "---- SSS-DYNBUILD v5  " (menucmd "M=$(edtime,$(getvar,date),YYYY-MO-DD HH:MM)")
                   "  AutoCAD " (getvar "ACADVER")))
  (sss:bclose-discard)
  (setq vars '("CMDECHO" "FILEDIA" "CMDDIA" "EXPERT" "ATTREQ" "OSMODE" "INSUNITS" "CLAYER" "PICKFIRST"
               "BACTIONBARMODE" "INSUNITSDEFSOURCE" "INSUNITSDEFTARGET"))
  (setq old (mapcar 'getvar vars))
  (mapcar 'setvar '("CMDECHO" "FILEDIA" "CMDDIA" "EXPERT" "ATTREQ" "OSMODE" "PICKFIRST"
                    "BACTIONBARMODE" "INSUNITSDEFSOURCE" "INSUNITSDEFTARGET")
          '(0 0 0 5 0 0 0 1 0 0))
  (setvar "CLAYER" "0")
  (setq fams (sss:families) done 0 failed '())
  (foreach f fams
    (if (or (null pick) (member (sss:get f 1) pick))
      (progn
        (setq r (vl-catch-all-apply 'sss:build (list f)))
        (if (vl-catch-all-error-p r)
          (progn
            (sss:log (strcat "  FAIL " (sss:get f 1) ": " (vl-catch-all-error-message r)))
            (setq failed (cons (sss:get f 1) failed))
            (sss:finish)
            (sss:bclose-discard))
          (setq done (1+ done))))))
  (mapcar 'setvar vars old)
  (command "_.ZOOM" "_E")
  (sss:log (strcat (itoa done) " families built, " (itoa (length failed)) " stopped"
                   (if failed (strcat ": " (sss:join (reverse failed) ", ")) "")
                   ". Check the PASS / FAIL lines above, then SAVE and send the drawing."))
  (close *sss-log*)
  (setq *sss-log* nil)
  (princ))

(defun c:SSSDYNTEST () (sss:run '("TURN ARROW" "CROSSWALK CONTINENTAL" "BIKE XING GREEN" "SIGNAL HEAD RYG")))
(defun c:SSSDYNBUILD () (sss:run nil))
(defun c:SSSDYNONE (/ n) (if (/= "" (setq n (getstring T "\nBlock name (for example STOP or TURN ARROW): "))) (sss:run (list (strcase n)))))

(princ "\nSSS-DYNBUILD v5 loaded. SSSDYNTEST builds four samples; SSSDYNBUILD builds them all.")
(princ)
