FROM python:3.10.0-slim

# Install build tools including git, gcc (C) and g++ (C++)
RUN apt-get update \
    && apt-get install -y git gcc g++ \
    && apt-get clean
    
RUN pip install --upgrade pip
RUN git clone https://github.com/GoogleCloudPlatform/professional-services-data-validator.git
WORKDIR professional-services-data-validator
RUN pip install . -v
ENTRYPOINT ["python","-m","data_validation"]
