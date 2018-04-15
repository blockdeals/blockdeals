FROM python:alpine3.6

ENV BLOCKDEALS_SETTINGS="/blockdeals/blockdeals.cfg"
EXPOSE 8000

RUN set -x \
  && apk add -U build-base openssl-dev git

ADD . /blockdeals
WORKDIR /blockdeals

ENTRYPOINT ["gunicorn"]
CMD ["-w", "8", "-k", "gevent", "-b", "0.0.0.0:8000", "--log-level=info", "--access-logfile=-", "wsgi:app"]

RUN set -x \
  && pip install -r requirements.txt
