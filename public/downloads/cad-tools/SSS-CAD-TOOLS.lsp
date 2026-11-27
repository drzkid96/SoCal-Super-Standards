;;; SSS-CAD-TOOLS.lsp  ·  SoCal Super Standards block tools for AutoCAD
;;;
;;; SSSDYNEXPORT
;;;   Copies every dynamic block in the current drawing into one clean library drawing,
;;;   <drawing name>-SSS-DYNAMIC.dwg, beside the current drawing, plus a CSV of each block's
;;;   dynamic properties (visibility states, flips, rotations, lengths and their allowed values).
;;;   AutoCAD writes the library, so parameters, actions and visibility states stay intact.
;;;   In the copy, block geometry moves to layer 0 with ByBlock linetype and lineweight;
;;;   ByLayer colors become ByBlock, explicit colors (green bike fills) are kept, and geometry
;;;   on non-plotting layers moves to Defpoints so it still never plots. Names are cleaned and
;;;   prefixed (default PM-) with -DYN at the end. The current drawing is put back exactly as it
;;;   was when the command ends.
;;;
;;; Load with APPLOAD, then type SSSDYNEXPORT. Upload the DWG and CSV to publish them on SSS.

(vl-load-com)

(defun sss:clean-name (s / out i ch)
  (setq out "" i 1)
  (while (<= i (strlen s))
    (setq ch (substr s i 1)
          out (strcat out (if (wcmatch ch "[A-Za-z0-9]") (strcase ch) "-"))
          i (1+ i)))
  (while (vl-string-search "--" out) (setq out (vl-string-subst "-" "--" out)))
  (vl-string-trim "-" out))

(defun sss:dynamic-defs (doc / out)
  (vlax-for b (vla-get-Blocks doc)
    (if (and (= (vla-get-IsLayout b) :vlax-false)
             (= (vla-get-IsXRef b) :vlax-false)
             (= (vla-get-IsDynamicBlock b) :vlax-true)
             (not (wcmatch (vla-get-Name b) "`**")))
      (setq out (cons b out))))
  (reverse out))

(defun sss:noplot-p (doc name / lay)
  (setq lay (vl-catch-all-apply 'vla-Item (list (vla-get-Layers doc) name)))
  (and (not (vl-catch-all-error-p lay)) (= (vla-get-Plottable lay) :vlax-false)))

(defun sss:clean-def (doc b / lay col)
  (vlax-for e b
    (setq lay (vl-catch-all-apply 'vla-get-Layer (list e)))
    (if (not (vl-catch-all-error-p lay))
      (vl-catch-all-apply 'vla-put-Layer (list e (if (sss:noplot-p doc lay) "Defpoints" "0"))))
    (setq col (vl-catch-all-apply 'vla-get-Color (list e)))
    (if (and (not (vl-catch-all-error-p col)) (= col acByLayer))
      (vl-catch-all-apply 'vla-put-Color (list e acByBlock)))
    (vl-catch-all-apply 'vla-put-Linetype (list e "ByBlock"))
    (vl-catch-all-apply 'vla-put-Lineweight (list e acLnWtByBlock))))

(defun sss:variant->list (v)
  (if (and v (= (type v) 'variant)) (setq v (vlax-variant-value v)))
  (cond ((= (type v) 'safearray)
         (if (< (vlax-safearray-get-u-bound v 1) 0) nil (vlax-safearray->list v)))
        (v (list v))))

(defun sss:value->string (v)
  (if (= (type v) 'variant) (setq v (vlax-variant-value v)))
  (cond ((= (type v) 'safearray) "array")
        ((= (type v) 'str) v)
        ((numberp v) (rtos v 2 4))
        (t (vl-princ-to-string v))))

(defun sss:csv-field (s / i out ch)
  (setq out "" i 1)
  (while (<= i (strlen s))
    (setq ch (substr s i 1) out (strcat out (if (= ch "\"") "\"\"" ch)) i (1+ i)))
  (strcat "\"" out "\""))

(defun sss:properties (ref / out allowed)
  (foreach p (sss:variant->list (vla-GetDynamicBlockProperties ref))
    (if (and (= (vla-get-ReadOnly p) :vlax-false) (/= (vla-get-PropertyName p) "Origin"))
      (progn
        (setq allowed (mapcar 'sss:value->string (sss:variant->list (vla-get-AllowedValues p))))
        (setq out (cons (list (vla-get-PropertyName p) (sss:value->string (vla-get-Value p))
                              (if allowed (apply 'strcat (cons (car allowed) (mapcar '(lambda (a) (strcat "; " a)) (cdr allowed)))) ""))
                        out)))))
  (reverse out))

(defun c:SSSDYNEXPORT (/ doc ms defs prefix base file csv f x gap ref mn mx width objs sset name new used n arr)
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object))
        ms (vla-get-ModelSpace doc)
        defs (sss:dynamic-defs doc))
  (cond
    ((null defs) (princ "\nNo dynamic blocks in this drawing."))
    ((/= 1 (logand 1 (getvar "UNDOCTL")))
     (princ "\nUNDO is turned off, so this drawing could not be restored afterward. Run UNDO > All first."))
    (t
    (progn
      (setq prefix (getstring (strcat "\nName prefix <PM->: ")))
      (if (= prefix "") (setq prefix "PM-"))
      (setq base (strcat (getvar "DWGPREFIX") (vl-filename-base (getvar "DWGNAME")) "-SSS-DYNAMIC")
            file (strcat base ".dwg")
            csv (strcat base ".csv")
            x 0.0 gap 10.0 n 0)
      (command "_.UNDO" "_Mark")
      ;; clean and rename every definition in this session, then lay one reference of each out in a row
      (foreach b defs
        (sss:clean-def doc b)
        (setq name (vla-get-Name b)
              new (strcat (strcase prefix) (sss:clean-name name) "-DYN"))
        (if (and (/= new name) (not (tblsearch "BLOCK" new))) (vla-put-Name b new))
        (setq ref (vla-InsertBlock ms (vlax-3d-point x 0.0 0.0) (vla-get-Name b) 1.0 1.0 1.0 0.0))
        (vla-GetBoundingBox ref 'mn 'mx)
        (setq mn (vlax-safearray->list mn) mx (vlax-safearray->list mx)
              width (- (car mx) (car mn)))
        (vla-Move ref (vlax-3d-point (car mn) 0.0 0.0) (vlax-3d-point x 0.0 0.0))
        (setq objs (cons ref objs)
              used (cons (list (vla-get-Name b) (sss:properties ref)) used)
              x (+ x width gap)
              n (1+ n)))
      (if (findfile file) (vl-file-delete file))
      (setq arr (vlax-make-safearray vlax-vbObject (cons 0 (1- (length objs)))))
      (vlax-safearray-fill arr (reverse objs))
      (setq sset (vla-Add (vla-get-SelectionSets doc) (strcat "SSSWB" (rtos (getvar "CDATE") 2 6))))
      (vla-AddItems sset arr)
      (vla-WBlock doc file sset)
      (vla-Delete sset)
      ;; property list for the SSS catalog
      (if (setq f (open csv "w"))
        (progn
          (write-line "block,property,current,allowed" f)
          (foreach row (reverse used)
            (if (cadr row)
              (foreach p (cadr row)
                (write-line (strcat (sss:csv-field (car row)) "," (sss:csv-field (car p)) "," (sss:csv-field (cadr p)) "," (sss:csv-field (caddr p))) f))
              (write-line (strcat (sss:csv-field (car row)) ",,,") f)))
          (close f)))
      ;; put this drawing back as it was
      (command "_.UNDO" "_Back")
      (princ (strcat "\n" (itoa n) " dynamic block(s) written to " file "\nProperties: " csv)))))
  (princ))

(princ "\nSSS-CAD-TOOLS loaded. Command: SSSDYNEXPORT")
(princ)
