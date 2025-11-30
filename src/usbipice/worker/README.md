## Worker setup

### Enable usbip 
```
sudo modprobe usbip_host
sudo modprobe usbip_core
sudo modprobe vhci_hcd
sudo usbipd -D
```

### Pythons deps 
```
pip install -r requirements.txt
```

### Environment Configuration
- USBIPICE_DATABASE to [psycopg connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)
- CLIENT_NAME to a unique value

### Run
```
python3 worker.py
```