import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

# email result
msg = MIMEMultipart()
msg['Subject'] = 'KU Leuven openbedrijvendag - uw mozaïek'
msg['From'] = 'superpi@cs.kuleuven.be'
msg['To'] = 'korneeldumon@gmail.com'
fp = open('output/mosaic_0.png', 'rb')
img = MIMEImage(fp.read())
fp.close()
msg.attach(img)

s = smtplib.SMTP('mail4.cs.kuleuven.be')
s.sendmail('asdfasdf@cs.kuleuven.be', [msg['To']], msg.as_string())
s.quit()
