FROM nginx:alpine
# Configuramos Nginx para que escuche en el 8080 porque tu orquestador lo espera ahí
RUN sed -i 's/listen[[:space:]]*80;/listen 8080;/g' /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
