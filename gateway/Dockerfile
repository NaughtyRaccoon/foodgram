FROM nginx:1.22.1
COPY nginx.conf /etc/nginx/templates/default.conf.template
RUN mkdir -p /staticfiles/media && chmod -R 755 /staticfiles/media
