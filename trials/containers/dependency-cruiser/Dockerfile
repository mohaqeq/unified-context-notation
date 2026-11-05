FROM node:20-slim
RUN npm install -g dependency-cruiser@16 typescript@5 && npm cache clean --force
WORKDIR /repo
ENTRYPOINT ["depcruise"]
