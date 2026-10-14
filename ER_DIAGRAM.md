# ER diagram and relational mapping

Open [`ER_DIAGRAM.svg`](ER_DIAGRAM.svg) for the visual ER model.

## Relationship mapping

| ER relationship | Relational implementation | Cardinality |
| --- | --- | --- |
| Customer owns vehicles | `VEHICLE.Customer_ID` → `CUSTOMER.Customer_ID` | One customer to many vehicles |
| Vehicle receives service | `SERVICE_RECORD.Vehicle_ID` → `VEHICLE.Vehicle_ID` | One vehicle to many service records |
| Mechanic performs service | `SERVICE_RECORD.Mechanic_ID` → `MECHANIC.Mechanic_ID` | One mechanic to many service records |
| Service type classifies job | `SERVICE_RECORD.Service_ID` → `SERVICE.Service_ID` | One catalogue service to many service records |
| Service record consumes parts | `SERVICE_PART.Service_Record_ID` → `SERVICE_RECORD.Service_Record_ID` | One service record to many part lines |
| Spare part appears in part lines | `SERVICE_PART.Part_ID` → `SPARE_PART.Part_ID` | One spare part to many usage lines |
| Service record is billed | `INVOICE.Service_Record_ID` → `SERVICE_RECORD.Service_Record_ID` with `UNIQUE` | One service record to zero or one invoice |

`SERVICE_PART` resolves the many-to-many relationship between service records and spare parts. All relationships use primary and foreign keys, and referenced records are restricted from deletion while dependent history exists.
