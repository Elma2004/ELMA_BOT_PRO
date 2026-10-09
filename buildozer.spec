[app]
title = ELMA BOT PRO
package.name = elmabotpro
package.domain = org.elma.bot
source.dir = .
source.include_exts = py,kv,json,png,jpg,jpeg,svg,txt
version = 3.0.1
requirements = python3,kivy==2.3.0,pyjnius,requests,urllib3,certifi,android
orientation = portrait
android.permissions = INTERNET,RECEIVE_SMS,READ_SMS,SEND_SMS,FOREGROUND_SERVICE,RECEIVE_BOOT_COMPLETED
android.api = 31
android.minapi = 21
android.services = sms_service:service.py
fullscreen = 1
p4a.branch = master
icon.filename = %(source.dir)s/icone.png

[buildozer]
log_level = 2
warn_on_root = 1
