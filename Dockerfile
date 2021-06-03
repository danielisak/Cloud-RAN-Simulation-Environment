FROM ubuntu:18.04

RUN apt-get update

# Install python dev-version and pip
RUN apt-get --yes --no-install-recommends install python3-dev
RUN apt-get --yes --no-install-recommends install python3-pip
RUN pip3 install --upgrade pip

# Create app dir
WORKDIR /app
COPY app.py /app

# Folder path in Docker image dir, COPY only copies contents of folder
COPY ./api /app/api
COPY ./ovs_connector/ovs_reconfig.json /app
COPY requirements.txt /app

# Install requirement for Python environment
RUN pip3 --no-cache-dir install -r requirements.txt

# Install https capabilities needed for coin-or-cbc solver
RUN apt-get install -y apt-transport-https
RUN apt-get install -y coinor-cbc

# Run pulptest making sure that cbc works
RUN pulptest

# Run command to start app
ENTRYPOINT [ "python3" ]
CMD ["app.py"]
