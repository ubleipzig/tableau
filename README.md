README
======

Displaying data and gathering feedback.

Build and run
-------------

* Install dependencies

        $ mkvirtualenv tableau
        (tableau)$ pip install -r requirements.txt


* Development

        (tableau)$ python tableau/app.py


* More serious

        (tableau)$ gunicorn tableau.app:app

Screenshot
----------

![Summary](http://i.imgur.com/06y7y9C.png)

![Settings](http://i.imgur.com/qMTU3Qu.png)

![Comparison](http://i.imgur.com/aAmwzNm.png)

![Details](http://i.imgur.com/y2nihvZ.png)