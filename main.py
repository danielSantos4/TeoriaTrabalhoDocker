from automata.tm.dtm import DTM
from fastapi import FastAPI, Request, Depends
from fastapi_mail import ConnectionConfig, MessageSchema, MessageType, FastMail
from sqlalchemy.orm import Session

from sql_app import crud, models, schemas
from sql_app.database import engine, SessionLocal
from util.email_body import EmailSchema

from prometheus_fastapi_instrumentator import Instrumentator

import pika, time, json
import asyncio
import multiprocessing


app = FastAPI()


models.Base.metadata.create_all(bind=engine)
Instrumentator().instrument(app).expose(app)

conf = ConnectionConfig(
    MAIL_USERNAME="c6d442e69bba7f",
    MAIL_PASSWORD="952f40a34ff356",
    MAIL_FROM="from@example.com",
    MAIL_PORT=2525,
    MAIL_SERVER="sandbox.smtp.mailtrap.io",
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)






# Patter Singleton
# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/get_history/{id}")
async def get_history(id: int, db: Session = Depends(get_db)):
    history = crud.get_history(db=db, id=id)
    if history is None:
        return {
            "code": "404",
            "msg": "not found"
        }
    return history


@app.get("/get_all_history")
async def get_all_history(db: Session = Depends(get_db)):
    history = crud.get_all_history(db=db)
    return history


@app.post("/dtm")
async def dtm(info: Request, db: Session = Depends(get_db)):
    info = await info.json()
    i = int(0)
    msg_final = ""
    for json_data in info:
        msg = ""
        states = set(json_data.get("states", []))

        if len(states) == 0:
            msg += "states cannot be empty   -    "
            
        input_symbols = set(json_data.get("input_symbols", []))
        if len(input_symbols) == 0:
            msg += "input_symbols cannot be empty   -    "
            
        tape_symbols = set(json_data.get("tape_symbols", []))
        if len(tape_symbols) == 0:
            msg += "tape_symbols cannot be empty   -    "

        initial_state = json_data.get("initial_state", "")
        if initial_state == "":
            msg += "initial_state cannot be empty   -    "
        
        blank_symbol = json_data.get("blank_symbol", "")
        if blank_symbol == "":
            msg += "blank_symbol cannot be empty   -    "
        
        final_states = set(json_data.get("final_states", []))
        if len(final_states) == 0:
            msg += "final_states cannot be empty   -    "
        
        transitions = dict(json_data.get("transitions", {}))
        if len(transitions) == 0:
            msg += "transitions cannot be empty   -    "

        input = json_data.get("input", "")
        if input == "":
            msg += "input cannot be empty   -    "
        #print(info)

        if( msg == ""):
            sender = await create_rabbitmq_connection()
            channel_sender = sender.channel()

            queue_name = 'nome_da_fila'
            channel_sender.queue_declare(queue=queue_name)

            channel_sender.basic_publish(exchange='',
                                routing_key=queue_name,
                                body=json.dumps(json_data))
            sender.close()
        msg_final += "MT - " + str(i) + "   -    " + msg
        i += 1
    msg_final = "info sobre as maquinas : - " + msg_final


    return msg_final

@app.get("/consume")
async def consumo( ):
    print("HERE2")
    connection = await create_rabbitmq_connection( )
    channel = connection.channel()

    channel.queue_declare(queue='nome_da_fila')
    

    def callback(ch, method, properties, body):
        return(body)
        

    while True:
        method_frame, header_frame, body = channel.basic_get(queue='nome_da_fila', auto_ack=True)
        if method_frame:
            callback(None, method_frame, None, body)
            print(body)
            MT = json.loads(body.decode())
            print(MT)
            await send_mail( MT )
            
        else:
            print("Não há mais mensagens na fila.")
            break

    connection.close()
    return "Fim do consumo"

async def send_mail(info):
    #info = await info.json()

    states = set(info.get("states", []))
    input_symbols = set(info.get("input_symbols", []))
    tape_symbols = set(info.get("tape_symbols", []))
    initial_state = info.get("initial_state", "")
    blank_symbol = info.get("blank_symbol", "")
    final_states = set(info.get("final_states", []))
    transitions = dict(info.get("transitions", {}))
    input = info.get("input", "")

    dtm = DTM(
        states=states,
        input_symbols=input_symbols,
        tape_symbols=tape_symbols,
        transitions=transitions,
        initial_state=initial_state,
        blank_symbol=blank_symbol,
        final_states=final_states,
    )
    if dtm.accepts_input(input):
        print('accepted')
        result = "accepted"
    else:
        print('rejected')
        result = "rejected"

    """history = schemas.History(query=str(info), result=result)
    crud.create_history(db=db, history=history)"""

    email_shema = EmailSchema(email=["to@example.com"])
    await simple_send(email_shema, result=result, configuration=str(info))



async def simple_send(email: EmailSchema, result: str, configuration: str):
    html = """
    <p>Thanks for using Fastapi-mail</p>
    <p> The result is: """ + result + """</p>
    <p> We have used this configuration: """ + configuration + """</p>
    """
    message = MessageSchema(
        subject="Fastapi-Mail module",
        recipients=email.dict().get("email"),
        body=html,
        subtype=MessageType.html)

    fm = FastMail(conf)
    await fm.send_message(message)
    return "OK"

async def create_rabbitmq_connection():
    return pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq',
    port=5672,
    credentials=pika.PlainCredentials('guest', 'guest'),
    heartbeat=5))



async def callback(ch, method, properties, body):
        print(" [x] Received %r" % body)
        email_shema = EmailSchema(email=["to@example.com"])
        await simple_send(email_shema, result="aceito", configuration="apenas testes :(")