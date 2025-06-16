FROM python:3.9-slim

WORKDIR /app

# Installa le dipendenze per mysqlclient e python-ldap
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    pkg-config \
    build-essential \
    libldap2-dev \
    libsasl2-dev \
    ldap-utils \
    gettext \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice dell'applicazione
COPY . .

# Esponi la porta su cui gira l'app
EXPOSE 8000

# Comando per avviare l'applicazione con timeout aumentato
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "300", "--workers", "4", "reti_project.wsgi:application"] 