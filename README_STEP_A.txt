CampusNest Phase 6 - STEP A (backend only)
==========================================
This ZIP contains ONLY the backend part of Phase 6. The frontend is NOT changed yet
(Steps B-E come later), so the website will look exactly the same as before.

FILES IN THIS ZIP
  backup_project.py                 (new)      put in:  New folder\
  backend\requirements.txt          (REPLACES the existing one)
  backend\app.py                    (REPLACES - 4 small additions, see below)
  backend\models.py                 (REPLACES - 1 new column)
  backend\validation.py             (REPLACES - 1 new optional field)
  backend\migrate_phase6.py         (new)
  backend\test_matching.py          (new)
  backend\test_phase6.py            (new)
  backend\matching\*.py             (new folder, 9 files)

NOT in this ZIP, and must stay as they are: permissions.py, test_phase4.py, test_phase5.py,
check_db.py, the frontend folder, the old Frontend folder, your venv and your database.

HOW TO APPLY (Windows). "New folder" is the folder that contains backend, frontend and venv.
1) BACK UP FIRST. Copy backup_project.py into New folder, then in Command Prompt:
       cd "C:\path\to\CampusNest\New folder"
       python backup_project.py
   Check that a folder appeared in  ...\CampusNest\CampusNest_backups\
2) Copy the files above into the same places (say "Yes" to replace app.py, models.py,
   validation.py and requirements.txt - the backup from step 1 has the originals).
3) Install the new packages (still in New folder):
       venv\Scripts\activate
       pip install -r backend\requirements.txt
   (If activate is blocked, use:  venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    and run every "python" below as  ..\venv\Scripts\python.exe )
4) If you already have a database, migrate it (makes its own backup, adds one empty column):
       cd backend
       python migrate_phase6.py
   If you do not have a database yet, skip this - the app creates everything.
5) Run the tests, in this order, from the backend folder:
       python test_matching.py
       python test_phase5.py
       python test_phase6.py
   Each ends with a line like  "N passed, 0 failed".  test_phase6.py also re-runs the other two.
6) Start the app as usual:   python app.py
