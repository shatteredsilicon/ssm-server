CREATE DATABASE IF NOT EXISTS orchestrator;
GRANT ALL PRIVILEGES ON orchestrator.* TO 'orchestrator'@'localhost' IDENTIFIED BY 'orchestrator';

CREATE DATABASE IF NOT EXISTS `ssm-managed`;
GRANT ALL PRIVILEGES ON `ssm-managed`.* TO "ssm-managed"@localhost IDENTIFIED BY "ssm-managed";

GRANT SELECT ON ssm.* TO 'grafana'@'localhost' IDENTIFIED BY 'N9mutoipdtlxutgi9rHIFnjM';

CREATE DATABASE IF NOT EXISTS ssm;
GRANT ALL PRIVILEGES ON ssm.* TO "qan-api"@localhost IDENTIFIED BY "qan-api";

ALTER TABLE `ssm`.`query_classes` ADD COLUMN IF NOT EXISTS `procedures` TEXT DEFAULT NULL;
ALTER TABLE `ssm`.`query_examples` ADD COLUMN IF NOT EXISTS `explain` TEXT DEFAULT NULL;
