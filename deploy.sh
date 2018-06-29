#!/bin/sh
cd ~/blockdeals
git pull \
  && docker build -t blockdeals . \
  && docker stop blockdeals \
  && docker rm blockdeals \
  && docker run -v /blockdeals.cfg:/blockdeals/blockdeals.cfg:ro --net web --link=mongo:mongodb --name=blockdeals --restart=unless-stopped -d blockdeals
