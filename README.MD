# How to run this on your machine
Get Python from https://www.python.org/downloads/
1. Open a terminal
2. Type in git clone https://github.com/natarajan1993/RSS-reader-backstitch
3. cd RSS-reader-backstitch
4. Type "source/venv/bin/activate"
5. cd rss_reader
6. Type "python manage.py migrate"
    - This will create the local database
7. OPTIONAL: Type "python manage.py createsuperuser" to create an admin account
    - Admin page can be accessed at http://localhost:8000/admin
8. Type "python manage.py runserver"
9. In a web browser go to http://localhost:8000/ to access the page