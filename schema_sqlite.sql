PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS `CUSTOMER` (
    `Customer_ID` INTEGER PRIMARY KEY AUTOINCREMENT,
    `Name` TEXT NOT NULL CHECK (length(trim(`Name`)) > 0),
    `Phone` TEXT,
    `Email` TEXT,
    `Address` TEXT
);

CREATE TABLE IF NOT EXISTS `VEHICLE` (
    `Vehicle_ID` INTEGER PRIMARY KEY AUTOINCREMENT,
    `Customer_ID` INTEGER NOT NULL,
    `Registration_No` TEXT NOT NULL UNIQUE,
    `Brand` TEXT,
    `Model` TEXT,
    `Manufacturing_Year` INTEGER CHECK (`Manufacturing_Year` IS NULL OR `Manufacturing_Year` BETWEEN 1886 AND 2100),
    `Vehicle_Type` TEXT NOT NULL DEFAULT 'Other',
    FOREIGN KEY (`Customer_ID`) REFERENCES `CUSTOMER` (`Customer_ID`) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS `MECHANIC` (
    `Mechanic_ID` INTEGER PRIMARY KEY AUTOINCREMENT,
    `Name` TEXT NOT NULL CHECK (length(trim(`Name`)) > 0),
    `Phone` TEXT,
    `Specialization` TEXT,
    `Experience` INTEGER NOT NULL DEFAULT 0 CHECK (`Experience` >= 0)
);

CREATE TABLE IF NOT EXISTS `SERVICE` (
    `Service_ID` INTEGER PRIMARY KEY AUTOINCREMENT,
    `Service_Name` TEXT NOT NULL UNIQUE CHECK (length(trim(`Service_Name`)) > 0),
    `Description` TEXT,
    `Labour_Cost` NUMERIC NOT NULL DEFAULT 0 CHECK (`Labour_Cost` >= 0),
    `Estimated_Time` TEXT
);

CREATE TABLE IF NOT EXISTS `SERVICE_RECORD` (
    `Service_Record_ID` INTEGER PRIMARY KEY AUTOINCREMENT,
    `Vehicle_ID` INTEGER NOT NULL,
    `Mechanic_ID` INTEGER NOT NULL,
    `Service_ID` INTEGER NOT NULL,
    `Service_Date` TEXT NOT NULL,
    `Problem_Description` TEXT,
    `Service_Status` TEXT NOT NULL DEFAULT 'Booked'
        CHECK (`Service_Status` IN ('Booked', 'In Progress', 'Completed', 'Cancelled')),
    `Remarks` TEXT,
    FOREIGN KEY (`Vehicle_ID`) REFERENCES `VEHICLE` (`Vehicle_ID`) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (`Mechanic_ID`) REFERENCES `MECHANIC` (`Mechanic_ID`) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (`Service_ID`) REFERENCES `SERVICE` (`Service_ID`) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS `SPARE_PART` (
    `Part_ID` INTEGER PRIMARY KEY AUTOINCREMENT,
    `Part_Name` TEXT NOT NULL CHECK (length(trim(`Part_Name`)) > 0),
    `Category` TEXT,
    `Unit_Price` NUMERIC NOT NULL DEFAULT 0 CHECK (`Unit_Price` >= 0),
    `Quantity_Available` INTEGER NOT NULL DEFAULT 0 CHECK (`Quantity_Available` >= 0),
    `Reorder_Level` INTEGER NOT NULL DEFAULT 5 CHECK (`Reorder_Level` >= 0)
);

CREATE TABLE IF NOT EXISTS `SERVICE_PART` (
    `Service_Part_ID` INTEGER PRIMARY KEY AUTOINCREMENT,
    `Service_Record_ID` INTEGER NOT NULL,
    `Part_ID` INTEGER NOT NULL,
    `Quantity_Used` INTEGER NOT NULL CHECK (`Quantity_Used` > 0),
    `Cost` NUMERIC NOT NULL CHECK (`Cost` >= 0),
    FOREIGN KEY (`Service_Record_ID`) REFERENCES `SERVICE_RECORD` (`Service_Record_ID`) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (`Part_ID`) REFERENCES `SPARE_PART` (`Part_ID`) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS `INVOICE` (
    `Invoice_ID` INTEGER PRIMARY KEY AUTOINCREMENT,
    `Service_Record_ID` INTEGER NOT NULL UNIQUE,
    `Invoice_Date` TEXT NOT NULL,
    `Labour_Amount` NUMERIC NOT NULL DEFAULT 0 CHECK (`Labour_Amount` >= 0),
    `Parts_Amount` NUMERIC NOT NULL DEFAULT 0 CHECK (`Parts_Amount` >= 0),
    `Tax` NUMERIC NOT NULL DEFAULT 0 CHECK (`Tax` >= 0),
    `Total_Amount` NUMERIC NOT NULL DEFAULT 0 CHECK (`Total_Amount` >= 0),
    `Payment_Status` TEXT NOT NULL DEFAULT 'Unpaid'
        CHECK (`Payment_Status` IN ('Unpaid', 'Partial', 'Paid')),
    FOREIGN KEY (`Service_Record_ID`) REFERENCES `SERVICE_RECORD` (`Service_Record_ID`) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS `idx_vehicle_customer` ON `VEHICLE` (`Customer_ID`);
CREATE INDEX IF NOT EXISTS `idx_service_record_vehicle_date` ON `SERVICE_RECORD` (`Vehicle_ID`, `Service_Date` DESC);
CREATE INDEX IF NOT EXISTS `idx_service_record_status` ON `SERVICE_RECORD` (`Service_Status`);
CREATE INDEX IF NOT EXISTS `idx_service_part_record` ON `SERVICE_PART` (`Service_Record_ID`);
CREATE INDEX IF NOT EXISTS `idx_invoice_payment_status` ON `INVOICE` (`Payment_Status`);

DROP VIEW IF EXISTS `V_SERVICE_HISTORY`;
CREATE VIEW `V_SERVICE_HISTORY` AS
SELECT
    sr.`Service_Record_ID`,
    sr.`Service_Date`,
    sr.`Service_Status`,
    sr.`Problem_Description`,
    sr.`Remarks`,
    v.`Vehicle_ID`,
    v.`Registration_No`,
    v.`Brand`,
    v.`Model`,
    v.`Vehicle_Type`,
    c.`Customer_ID`,
    c.`Name` AS `Customer_Name`,
    c.`Phone` AS `Customer_Phone`,
    m.`Mechanic_ID`,
    m.`Name` AS `Mechanic_Name`,
    s.`Service_ID`,
    s.`Service_Name`,
    s.`Labour_Cost`,
    COALESCE(i.`Invoice_ID`, 0) AS `Invoice_ID`,
    COALESCE(i.`Total_Amount`, 0) AS `Total_Amount`,
    i.`Payment_Status`
FROM `SERVICE_RECORD` sr
JOIN `VEHICLE` v ON v.`Vehicle_ID` = sr.`Vehicle_ID`
JOIN `CUSTOMER` c ON c.`Customer_ID` = v.`Customer_ID`
JOIN `MECHANIC` m ON m.`Mechanic_ID` = sr.`Mechanic_ID`
JOIN `SERVICE` s ON s.`Service_ID` = sr.`Service_ID`
LEFT JOIN `INVOICE` i ON i.`Service_Record_ID` = sr.`Service_Record_ID`;

DROP VIEW IF EXISTS `V_LOW_STOCK`;
CREATE VIEW `V_LOW_STOCK` AS
SELECT `Part_ID`, `Part_Name`, `Category`, `Unit_Price`, `Quantity_Available`, `Reorder_Level`
FROM `SPARE_PART`
WHERE `Quantity_Available` <= `Reorder_Level`;

DROP TRIGGER IF EXISTS `trg_service_part_validate_insert`;
DROP TRIGGER IF EXISTS `trg_service_part_after_insert`;
DROP TRIGGER IF EXISTS `trg_service_part_validate_update`;
DROP TRIGGER IF EXISTS `trg_service_part_after_update`;
DROP TRIGGER IF EXISTS `trg_service_part_after_delete`;

CREATE TRIGGER `trg_service_part_validate_insert`
BEFORE INSERT ON `SERVICE_PART`
FOR EACH ROW
BEGIN
    SELECT CASE
        WHEN NEW.`Quantity_Used` <= 0
        THEN RAISE(ABORT, 'Quantity used must be greater than zero')
    END;
    SELECT CASE
        WHEN COALESCE((SELECT `Quantity_Available` FROM `SPARE_PART` WHERE `Part_ID` = NEW.`Part_ID`), -1) < NEW.`Quantity_Used`
        THEN RAISE(ABORT, 'Insufficient spare-part stock')
    END;
END;

CREATE TRIGGER `trg_service_part_after_insert`
AFTER INSERT ON `SERVICE_PART`
FOR EACH ROW
BEGIN
    UPDATE `SPARE_PART`
    SET `Quantity_Available` = `Quantity_Available` - NEW.`Quantity_Used`
    WHERE `Part_ID` = NEW.`Part_ID`;
END;

CREATE TRIGGER `trg_service_part_validate_update`
BEFORE UPDATE ON `SERVICE_PART`
FOR EACH ROW
BEGIN
    SELECT CASE
        WHEN NEW.`Quantity_Used` <= 0
        THEN RAISE(ABORT, 'Quantity used must be greater than zero')
    END;
    SELECT CASE
        WHEN NEW.`Part_ID` = OLD.`Part_ID`
             AND COALESCE((SELECT `Quantity_Available` FROM `SPARE_PART` WHERE `Part_ID` = NEW.`Part_ID`), -1) + OLD.`Quantity_Used` < NEW.`Quantity_Used`
        THEN RAISE(ABORT, 'Insufficient spare-part stock')
    END;
    SELECT CASE
        WHEN NEW.`Part_ID` <> OLD.`Part_ID`
             AND COALESCE((SELECT `Quantity_Available` FROM `SPARE_PART` WHERE `Part_ID` = NEW.`Part_ID`), -1) < NEW.`Quantity_Used`
        THEN RAISE(ABORT, 'Insufficient spare-part stock')
    END;
END;

CREATE TRIGGER `trg_service_part_after_update`
AFTER UPDATE ON `SERVICE_PART`
FOR EACH ROW
BEGIN
    UPDATE `SPARE_PART`
    SET `Quantity_Available` = `Quantity_Available` + OLD.`Quantity_Used`
    WHERE `Part_ID` = OLD.`Part_ID`;
    UPDATE `SPARE_PART`
    SET `Quantity_Available` = `Quantity_Available` - NEW.`Quantity_Used`
    WHERE `Part_ID` = NEW.`Part_ID`;
END;

CREATE TRIGGER `trg_service_part_after_delete`
AFTER DELETE ON `SERVICE_PART`
FOR EACH ROW
BEGIN
    UPDATE `SPARE_PART`
    SET `Quantity_Available` = `Quantity_Available` + OLD.`Quantity_Used`
    WHERE `Part_ID` = OLD.`Part_ID`;
END;
