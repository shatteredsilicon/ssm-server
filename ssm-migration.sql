CREATE DATABASE IF NOT EXISTS `ssm-managed`;
GRANT ALL PRIVILEGES ON `ssm-managed`.* TO "ssm-managed"@localhost IDENTIFIED BY "ssm-managed";

GRANT SELECT ON ssm.* TO 'grafana'@'localhost' IDENTIFIED BY 'N9mutoipdtlxutgi9rHIFnjM';

CREATE DATABASE IF NOT EXISTS ssm;
GRANT ALL PRIVILEGES ON ssm.* TO "qan-api"@localhost IDENTIFIED BY "qan-api";

ALTER TABLE `ssm`.`query_classes` ADD COLUMN IF NOT EXISTS `procedures` TEXT DEFAULT NULL;
ALTER TABLE `ssm`.`query_classes` ADD COLUMN IF NOT EXISTS `metadata` TEXT DEFAULT NULL;
ALTER TABLE `ssm`.`query_examples` ADD COLUMN IF NOT EXISTS `explain` TEXT DEFAULT NULL;
ALTER TABLE `ssm`.`query_examples` ADD COLUMN IF NOT EXISTS `metadata` TEXT DEFAULT NULL;

ALTER TABLE `ssm`.`query_class_metrics`
ADD INDEX instance_start (instance_id, start_ts),
ALGORITHM=INPLACE, LOCK=NONE;

CREATE TABLE IF NOT EXISTS `ssm`.`user_classes` (
  id    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user  VARCHAR(80) NOT NULL,
  host  VARCHAR(60) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY (user, host)
);

CREATE TABLE IF NOT EXISTS `ssm`.`query_user_sources` (
  query_class_id  INT UNSIGNED NOT NULL,
  instance_id     INT UNSIGNED NOT NULL,
  user_class_id   INT UNSIGNED NOT NULL,
  ts              TIMESTAMP NOT NULL,
  count           INT UNSIGNED NOT NULL,
  PRIMARY KEY (query_class_id, instance_id, user_class_id, ts)
);

CREATE TABLE IF NOT EXISTS `ssm`.`query_explain_indexes` (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  instance_id     INT UNSIGNED NOT NULL,
  query_class_id  INT UNSIGNED NOT NULL,
  example_period  TIMESTAMP NOT NULL,
  catalog_name    VARCHAR(63) NOT NULL DEFAULT '' COMMENT 'for postgresql only',
  schema_name     VARCHAR(63) NOT NULL,
  table_name      VARCHAR(255) NOT NULL COMMENT 'also for MongoDB collection',
  index_name      VARCHAR(255) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE INDEX (instance_id, query_class_id, example_period, schema_name, table_name, index_name),
  INDEX (schema_name, table_name, index_name, instance_id)
) CHARSET='utf8';

CREATE USER IF NOT EXISTS 'ssm'@'localhost' IDENTIFIED BY 'ssm' WITH MAX_USER_CONNECTIONS 10;
GRANT SELECT, PROCESS, SUPER, REPLICATION CLIENT, RELOAD ON *.* TO 'ssm'@'localhost';
GRANT SELECT, UPDATE, DELETE, DROP ON performance_schema.* TO 'ssm'@'localhost';
