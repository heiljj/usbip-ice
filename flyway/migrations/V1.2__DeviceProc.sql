CREATE PROCEDURE addDevice(deviceserial varchar(255), Worker varchar(255))
LANGUAGE plpgsql
AS
$$
BEGIN
    IF Worker NOT IN (SELECT WorkerName FROM Worker) THEN
        RAISE EXCEPTION 'Worker does not exist';
    END IF;

    IF deviceserial IN (SELECT SerialId FROM Device) THEN
        RAISE EXCEPTION 'Device serial already exists';
    END IF;

    INSERT INTO Device(SerialID, Worker, UsbipBus, LastUsbipExport, DeviceStatus)
    VALUES(deviceserial, Worker, NULL, NULL, 'await_flash_default');
END
$$;

CREATE PROCEDURE updateDeviceStatus(deviceserial varchar(255), dstate DeviceState)
LANGUAGE plpgsql
AS
$$
BEGIN
    IF deviceserial NOT IN (SELECT SerialId FROM Device) THEN
        RAISE EXCEPTION 'Device serial does not exist';
    END IF;

    UPDATE Device
    SET DeviceStatus = dstate
    WHERE SerialID = deviceserial;
END
$$;

CREATE PROCEDURE updateDeviceBus(deviceserial varchar(255), Bus varchar(10))
LANGUAGE plpgsql
AS
$$
BEGIN
    IF deviceserial NOT IN (SELECT SerialId FROM Device) THEN
        RAISE EXCEPTION 'Device serial does not exist';
    END IF;

    UPDATE Device
    SET UsbipBus = Bus,
        LastUsbipExport = CURRENT_TIMESTAMP 
    WHERE SerialID = deviceserial;
END
$$;

CREATE PROCEDURE removeDeviceBus(deviceserial varchar(255))
LANGUAGE plpgsql
AS
$$
BEGIN
    IF deviceserial NOT IN (SELECT SerialID FROM Device) THEN
        RAISE EXCEPTION 'Device serial does not exist';
    END IF;

    UPDATE Device
    SET UsbipBus = NULL
    WHERE SerialID = deviceserial;
END
$$;
