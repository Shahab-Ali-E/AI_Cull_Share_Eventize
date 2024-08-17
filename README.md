# important commands 
`1. TO RUN SERVER :->poetry run uvicorn src.main.main:app --reload`

`2.  TO RUN TEST CASES :->poetry run pytest -v`

`3.  TO USE ALEMBIC :->alembic init alembic(name according to yours)`

`4. TO RUN MIGRATIONS:->alembic revision --autogenerate -m "(whatever you want to nama i.e "First migrations")"`

`5. to upgrade the head :-> alembic upgrade head`

`6. to run rq worker open separate terminal and navigate to the file in which you've configure its server and you vevn must be activated before after run this :-> rq worker task_queue`

`7. to run CELERY open new terminal and activate your venv and then hit this command :-> celery -A src.main.main.celery worker --loglevel=info --pool=solo`

`8. To run flower use this command :->celery -A src.main.main.celery flower --port=5555`

`9. To clear poetry cache :-> poetry cache clear --all`

`10. To run rabbitmq-server open "RabbitMQ Command Prompt (sbindir)":-> rabbitmq-server start`


# Local running servers
`1. RabbitMQ was running on http://localhost:15672/`

"""you need to install torch by this command"""
`pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121`
