-- Run against an existing MySQL database selected by DB_NAME.
-- The application executes this file at startup using the configured database connection.

CREATE TABLE IF NOT EXISTS `CUSTOMER` (
    `Customer_ID` INT AUTO_INCREMENT PRIMARY KEY,
    `Name` VARCHAR(100) NOT NULL,
    `Phone` VARCHAR(20),
    `Email` VARCHAR(120),
    `Address` VARCHAR(255),
    CONSTRAINT `chk_customer_name` CHECK (CHAR_LENGTH(TRIM(`Name`)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `VEHICLE` (
    `Vehicle_ID` INT AUTO_INCREMENT PRIMARY KEY,
    `Customer_ID` INT NOT NULL,
    `Registration_No` VARCHAR(24) NOT NULL UNIQUE,
    `Brand` VARCHAR(60),
    `Model` VARCHAR(60),
    `Manufacturing_Year` SMALLINT,
    `Vehicle_Type` VARCHAR(30) NOT NULL DEFAULT 'Other',
    CONSTRAINT `chk_vehicle_year` CHECK (`Manufacturing_Year` IS NULL OR `Manufacturing_Year` BETWEEN 1886 AND 2100),
    KEY `idx_vehicle_customer` (`Customer_ID`),
    CONSTRAINT `fk_vehicle_customer` FOREIGN KEY (`Customer_ID`) REFERENCES `CUSTOMER` (`Customer_ID`) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `MECHANIC` (
    `Mechanic_ID` INT AUTO_INCREMENT PRIMARY KEY,
    `Name` VARCHAR(100) NOT NULL,
    `Phone` VARCHAR(20),
    `Specialization` VARCHAR(100),
    `Experience` INT NOT NULL DEFAULT 0,
    CONSTRAINT `chk_mechanic_experience` CHECK (`Experience` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `SERVICE` (
    `Service_ID` INT AUTO_INCREMENT PRIMARY KEY,
    `Service_Name` VARCHAR(100) NOT NULL UNIQUE,
    `Description` VARCHAR(500),
    `Labour_Cost` DECIMAL(10,2) NOT NULL DEFAULT 0,
    `Estimated_Time` VARCHAR(50),
    CONSTRAINT `chk_service_labour_cost` CHECK (`Labour_Cost` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `SERVICE_RECORD` (
    `Service_Record_ID` INT AUTO_INCREMENT PRIMARY KEY,
    `Vehicle_ID` INT NOT NULL,
    `Mechanic_ID` INT NOT NULL,
    `Service_ID` INT NOT NULL,
    `Service_Date` DATE NOT NULL,
    `Problem_Description` VARCHAR(500),
    `Service_Status` VARCHAR(30) NOT NULL DEFAULT 'Booked',
    `Remarks` VARCHAR(500),
    CONSTRAINT `chk_service_record_status` CHECK (`Service_Status` IN ('Booked', 'In Progress', 'Completed', 'Cancelled')),
    KEY `idx_service_record_vehicle_date` (`Vehicle_ID`, `Service_Date` DESC),
    KEY `idx_service_record_status` (`Service_Status`),
    CONSTRAINT `fk_record_vehicle` FOREIGN KEY (`Vehicle_ID`) REFERENCES `VEHICLE` (`Vehicle_ID`) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_record_mechanic` FOREIGN KEY (`Mechanic_ID`) REFERENCES `MECHANIC` (`Mechanic_ID`) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_record_service` FOREIGN KEY (`Service_ID`) REFERENCES `SERVICE` (`Service_ID`) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `SPARE_PART` (
    `Part_ID` INT AUTO_INCREMENT PRIMARY KEY,
    `Part_Name` VARCHAR(120) NOT NULL,
    `Category` VARCHAR(60),
    `Unit_Price` DECIMAL(10,2) NOT NULL DEFAULT 0,
    `Quantity_Available` INT NOT NULL DEFAULT 0,
    `Reorder_Level` INT NOT NULL DEFAULT 5,
    CONSTRAINT `chk_part_price` CHECK (`Unit_Price` >= 0),
    CONSTRAINT `chk_part_quantity` CHECK (`Quantity_Available` >= 0),
    CONSTRAINT `chk_part_reorder` CHECK (`Reorder_Level` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `SERVICE_PART` (
    `Service_Part_ID` INT AUTO_INCREMENT PRIMARY KEY,
    `Service_Record_ID` INT NOT NULL,
    `Part_ID` INT NOT NULL,
    `Quantity_Used` INT NOT NULL,
    `Cost` DECIMAL(10,2) NOT NULL,
    CONSTRAINT `chk_service_part_quantity` CHECK (`Quantity_Used` > 0),
    CONSTRAINT `chk_service_part_cost` CHECK (`Cost` >= 0),
    KEY `idx_service_part_record` (`Service_Record_ID`),
    CONSTRAINT `fk_service_part_record` FOREIGN KEY (`Service_Record_ID`) REFERENCES `SERVICE_RECORD` (`Service_Record_ID`) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_service_part_part` FOREIGN KEY (`Part_ID`) REFERENCES `SPARE_PART` (`Part_ID`) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `INVOICE` (
    `Invoice_ID` INT AUTO_INCREMENT PRIMARY KEY,
    `Service_Record_ID` INT NOT NULL UNIQUE,
    `Invoice_Date` DATE NOT NULL,
    `Labour_Amount` DECIMAL(10,2) NOT NULL DEFAULT 0,
    `Parts_Amount` DECIMAL(10,2) NOT NULL DEFAULT 0,
    `Tax` DECIMAL(10,2) NOT NULL DEFAULT 0,
    `Total_Amount` DECIMAL(10,2) NOT NULL DEFAULT 0,
    `Payment_Status` VARCHAR(30) NOT NULL DEFAULT 'Unpaid',
    CONSTRAINT `chk_invoice_labour` CHECK (`Labour_Amount` >= 0),
    CONSTRAINT `chk_invoice_parts` CHECK (`Parts_Amount` >= 0),
    CONSTRAINT `chk_invoice_tax` CHECK (`Tax` >= 0),
    CONSTRAINT `chk_invoice_total` CHECK (`Total_Amount` >= 0),
    CONSTRAINT `chk_invoice_status` CHECK (`Payment_Status` IN ('Unpaid', 'Partial', 'Paid')),
    KEY `idx_invoice_payment_status` (`Payment_Status`),
    CONSTRAINT `fk_invoice_record` FOREIGN KEY (`Service_Record_ID`) REFERENCES `SERVICE_RECORD` (`Service_Record_ID`) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP VIEW IF EXISTS `V_SERVICE_HISTORY`;
CREATE VIEW `V_SERVICE_HISTORY` AS
SELECT
    sr.`Service_Record_ID`, sr.`Service_Date`, sr.`Service_Status`,
    sr.`Problem_Description`, sr.`Remarks`,
    v.`Vehicle_ID`, v.`Registration_No`, v.`Brand`, v.`Model`, v.`Vehicle_Type`,
    c.`Customer_ID`, c.`Name` AS `Customer_Name`, c.`Phone` AS `Customer_Phone`,
    m.`Mechanic_ID`, m.`Name` AS `Mechanic_Name`,
    s.`Service_ID`, s.`Service_Name`, s.`Labour_Cost`,
    COALESCE(i.`Invoice_ID`, 0) AS `Invoice_ID`,
    COALESCE(i.`Total_Amount`, 0) AS `Total_Amount`, i.`Payment_Status`
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

DELIMITER $$
CREATE TRIGGER `trg_service_part_validate_insert`
BEFORE INSERT ON `SERVICE_PART`
FOR EACH ROW
BEGIN
    DECLARE v_stock INT DEFAULT NULL;
    SELECT `Quantity_Available` INTO v_stock
    FROM `SPARE_PART` WHERE `Part_ID` = NEW.`Part_ID` FOR UPDATE;
    IF NEW.`Quantity_Used` <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Quantity used must be greater than zero';
    END IF;
    IF v_stock IS NULL OR v_stock < NEW.`Quantity_Used` THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Insufficient spare-part stock';
    END IF;
END$$

CREATE TRIGGER `trg_service_part_after_insert`
AFTER INSERT ON `SERVICE_PART`
FOR EACH ROW
BEGIN
    UPDATE `SPARE_PART`
    SET `Quantity_Available` = `Quantity_Available` - NEW.`Quantity_Used`
    WHERE `Part_ID` = NEW.`Part_ID`;
END$$

CREATE TRIGGER `trg_service_part_validate_update`
BEFORE UPDATE ON `SERVICE_PART`
FOR EACH ROW
BEGIN
    DECLARE v_stock INT DEFAULT NULL;
    IF NEW.`Quantity_Used` <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Quantity used must be greater than zero';
    END IF;
    SELECT `Quantity_Available` INTO v_stock
    FROM `SPARE_PART` WHERE `Part_ID` = NEW.`Part_ID` FOR UPDATE;
    IF NEW.`Part_ID` = OLD.`Part_ID` THEN
        IF v_stock IS NULL OR v_stock + OLD.`Quantity_Used` < NEW.`Quantity_Used` THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Insufficient spare-part stock';
        END IF;
    ELSE
        IF v_stock IS NULL OR v_stock < NEW.`Quantity_Used` THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Insufficient spare-part stock';
        END IF;
    END IF;
END$$

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
END$$

CREATE TRIGGER `trg_service_part_after_delete`
AFTER DELETE ON `SERVICE_PART`
FOR EACH ROW
BEGIN
    UPDATE `SPARE_PART`
    SET `Quantity_Available` = `Quantity_Available` + OLD.`Quantity_Used`
    WHERE `Part_ID` = OLD.`Part_ID`;
END$$
DELIMITER ;
