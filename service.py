import json
import time
from pathlib import Path

from jnius import autoclass
from android.broadcast import BroadcastReceiver, IntentFilter

BASE = Path(__file__).resolve().parent
BRAIN_FILE = BASE / "subconscient_elma.json"

def load_brain():
    try:
        with open(BRAIN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"regles": [], "connaissances_apprises": [], "parametres": {}}

def normalize(value):
    return str(value).lower().strip()

def find_local_reply(brain, message):
    msg = normalize(message)
    for rule in brain.get("regles", []):
        for trigger in rule.get("declencheurs", []):
            if normalize(trigger) == msg:
                replies = rule.get("reponses", [])
                if replies:
                    import random
                    return random.choice(replies)
    return None

SmsManager = autoclass("android.telephony.SmsManager")

def on_sms(context, intent):
    try:
        if intent.getAction() != "android.provider.Telephony.SMS_RECEIVED":
            return
        extras = intent.getExtras()
        if not extras:
            return
        pdus = extras.get("pdus")
        if not pdus:
            return

        sender = None
        body_parts = []
        SmsMessage = autoclass("android.telephony.SmsMessage")
        for pdu in pdus:
            msg = SmsMessage.createFromPdu(pdu)
            if msg:
                sender = msg.getOriginatingAddress()
                body_parts.append(msg.getMessageBody() or "")
        body = "".join(body_parts)

        brain = load_brain()
        reply = find_local_reply(brain, body)
        if reply and sender:
            SmsManager.getDefault().sendTextMessage(sender, None, reply, None, None)
    except Exception:
        pass

receiver = BroadcastReceiver(on_broadcast=on_sms)
receiver.start(
    IntentFilter("android.provider.Telephony.SMS_RECEIVED")
)

while True:
    time.sleep(10)
