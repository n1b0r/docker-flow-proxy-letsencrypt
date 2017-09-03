FROM cilerler/mkdocs AS build
RUN pip install pygments && pip install pymdown-extensions
ADD . /docs
RUN mkdocs build --site-dir /site

FROM nginx:alpine
COPY --from=build /site /usr/share/nginx/html