# How to run this on your machine
Get Python from https://www.python.org/downloads/
1. Open a terminal
2. Type in git clone https://github.com/natarajan1993/RSS-reader-backstitch
3. cd RSS-reader-backstitch
4. Type "source/venv/bin/activate"
5. Type "pip install -r requirements.txt"
    - If you get an error that pip cannot be found, type "sudo easy_install pip"
    - It should come installed by default on Windows
6. cd rss_reader
7. Type "python manage.py migrate"
    - This will create the local database
8. OPTIONAL: Type "python manage.py createsuperuser" to create an admin account
    - Admin page can be accessed at http://localhost:8000/admin
9. Type "python manage.py runserver"
10. In a web browser go to http://localhost:8000/ to access the page
