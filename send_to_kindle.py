import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
import getpass
import os
from os import listdir
from os.path import isfile, join, basename

MAX_SIZE = 25000000
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
user_mail = input('Enter your email: ')
pswd = getpass.getpass('Password:')
kindle_mail = input('Enter kindle mail: ')
file_size = 0
sum_size = 0
server.login(user_mail, pswd)
send_from = user_mail
send_to = kindle_mail
msg = MIMEMultipart()
msg['From'] = user_mail
msg['To'] = kindle_mail
msg['Subject'] = 'Convertir'




incompatible_file = False
incompatible_format = ['.doc', '.docx', '.rtf', '.htm', '.html', '.txt', '.zip', '.mobi', '.jpg', '.gif', '.bmp',
                       '.png']
files = []
files.extend([os.getcwd() + "/" + f for f in listdir(os.getcwd()) if
              isfile(join(os.getcwd(), f)) and basename(f) != 'carga_kindle.py' and basename(f) != '.DS_Store'])

for f in files:
    file_name=basename(f)
    # check file format
    for s in incompatible_format:
        if s in file_name:
            print("true")
            incompatible_file=True
            break

    with open(f, "rb") as fil:
        if not incompatible_file:
            if (file_name != 'carga_kindle.py' and file_name != '.DS_Store'):
                file_stat = os.stat(f)
                file_size = file_stat.st_size
                sum_size += file_size

                # if it´s possible attach more files
                if (sum_size < MAX_SIZE and file_size < MAX_SIZE):
                    part = MIMEApplication(fil.read(), Name=file_name)
                    part['Content-Disposition'] = 'attachment; filename="%s"' % file_name
                    msg.attach(part)
                    print(f, " ", file_size / 1000000, " ", sum_size / 1000000)

                ## new mail because sum of sizes is greater than attachment max size
                if (sum_size >= MAX_SIZE and file_size < MAX_SIZE):
                    #send mail until here
                    print("sending mail", "\n")
                    server.sendmail(send_from, send_to, msg.as_string())
                    sum_size = file_size
                    print(f, " ", file_size / 1000000, " ", sum_size / 1000000)
                    #build new mail
                    msg = MIMEMultipart()
                    msg['From'] = user_mail
                    msg['To'] = kindle_mail
                    msg['Subject'] = 'Convertir'
                    part = MIMEApplication(fil.read(), Name=file_name)
                    part['Content-Disposition'] = 'attachment; filename="%s"' % file_name
                    msg.attach(part)
        else:
            print("Incompatible: ", file_name)
            incompatible_file = False

    # if last file send mail
    if (sum_size < MAX_SIZE and file_size < MAX_SIZE and files[-1] == f):
        print("Reached end of folder...\nSending mail... ")
        server.sendmail(send_from, send_to, msg.as_string())

server.close()
