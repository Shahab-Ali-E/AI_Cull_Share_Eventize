FROM python:3.12

#make work directory
WORKDIR /AI_CULL_SHARE_EVENTIZE

#install poetry 
RUN pip install poetry

#copy proejct dependices into workdir
COPY ./poetry.lock pyproject.toml /AI_CULL_SHARE_EVENTIZE/

#copy rest of the project   
COPY . /AI_CULL_SHARE_EVENTIZE/

#RUN
RUN poetry install

#EXPOSE
EXPOSE 8000

CMD [ "poetry", "run", "uvicorn", "src.main.main:app", "--reload", ""]