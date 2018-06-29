#!/bin/sh
cd ~/blockdeals
git pull \
  && docker build -t blockdeals . \
  && docker stop blockdeals \
  && docker rm blockdeals \
  && docker run -v /blockdeals.cfg:/blockdeals/blockdeals.cfg:ro --link=mongo:mongodb --name=blockdeals --restart=unless-stopped --net web -d blockdeals
