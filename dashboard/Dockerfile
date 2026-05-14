FROM node:22-alpine

WORKDIR /app

# Copy package configs first for caching
COPY package*.json ./

RUN npm install

# Copy remaining application files
COPY . .

EXPOSE 3001

CMD ["npm", "run", "dev"]
