# opensearch/Dockerfile
FROM opensearchproject/opensearch:3.4.0

# Install ICU analysis plugin (requires restart; baked into image here)
RUN /usr/share/opensearch/bin/opensearch-plugin install --batch analysis-icu
