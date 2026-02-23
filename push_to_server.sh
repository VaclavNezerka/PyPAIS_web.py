# copy the necessary files to the server
# scp -r static translations templates models silhada2@webhost-03.fsv.cvut.cz:~/aibal.fsv.cvut.cz/app
# scp -r requirements.txt app_report_exporter.py app_similarity_controller.py app.py db_api.py models.py forms.py silhada2@webhost-03.fsv.cvut.cz:~/aibal.fsv.cvut.cz/app
scp -r static translations templates models requirements.txt gunicorn.conf.py cleanup_sessions.py app_report_exporter.py app_similarity_controller.py app.py db_api.py models.py forms.py silhada2@webhost-03.fsv.cvut.cz:~/aibal.fsv.cvut.cz/app