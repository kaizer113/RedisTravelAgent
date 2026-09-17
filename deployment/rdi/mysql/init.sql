-- Fictional offers. MySQL is the intended price/inventory source of truth.
USE value_travel;
CREATE TABLE IF NOT EXISTS offers (
  package_id VARCHAR(16) PRIMARY KEY,
  name VARCHAR(160) NOT NULL,
  destination VARCHAR(80) NOT NULL,
  total_price DECIMAL(10,2) NOT NULL,
  available_rooms INT UNSIGNED NOT NULL,
  eligible_reward_base DECIMAL(10,2) NOT NULL,
  cancellation VARCHAR(512) NOT NULL,
  departure_date VARCHAR(10) NOT NULL,
  data_label VARCHAR(80) NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6)
);
REVOKE ALL PRIVILEGES ON `value\_travel`.* FROM 'value_travel_cdc'@'%';
GRANT SELECT, RELOAD, SHOW DATABASES, REPLICATION SLAVE, REPLICATION CLIENT
  ON *.* TO 'value_travel_cdc'@'%';
FLUSH PRIVILEGES;
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-001', 'Kaanapali Family Escape', 'Maui', 5890, 4, 4712.0, 'Refundable hotel until 30 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-002', 'Wailea Ocean Retreat', 'Maui', 6490, 5, 5192.0, 'Refundable hotel until 30 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-003', 'Kihei Beachside Value', 'Maui', 4790, 6, 3832.0, 'Hotel becomes nonrefundable 14 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-004', 'Waikiki Discovery', 'Oahu', 4390, 7, 3512.0, 'Refundable hotel until 30 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-005', 'Ko Olina Lagoon Stay', 'Oahu', 6290, 8, 5032.0, 'Refundable hotel until 30 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-006', 'Kona Coast Adventure', 'Hawaii', 5790, 9, 4632.0, 'Hotel becomes nonrefundable 14 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-007', 'Riviera Maya All-Inclusive', 'Cancun', 5290, 3, 4232.0, 'Refundable hotel until 30 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-008', 'Los Cabos Family Sun', 'Los Cabos', 4890, 4, 3912.0, 'Refundable hotel until 30 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-009', 'Pacific Couples Hideaway', 'Los Cabos', 3790, 5, 3032.0, 'Hotel becomes nonrefundable 14 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-010', 'Riviera Serenity', 'Cancun', 4290, 6, 3432.0, 'Refundable hotel until 30 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-011', 'Wailea Couples Escape', 'Maui', 4590, 7, 3672.0, 'Refundable hotel until 30 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-012', 'Kapalua Quiet Coast', 'Maui', 3990, 8, 3192.0, 'Hotel becomes nonrefundable 14 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-013', 'Aruba Beach Retreat', 'Aruba', 4690, 9, 3752.0, 'Refundable hotel until 30 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-014', 'Lisbon Neighborhoods', 'Lisbon', 3690, 3, 2952.0, 'Refundable hotel until 30 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-015', 'Rome and Florence', 'Italy', 4890, 4, 3912.0, 'Hotel becomes nonrefundable 14 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-016', 'Barcelona City and Sea', 'Barcelona', 4090, 5, 3272.0, 'Refundable hotel until 30 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-017', 'Paris Walkable Weekend', 'Paris', 3890, 6, 3112.0, 'Refundable hotel until 30 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
INSERT IGNORE INTO offers (package_id, name, destination, total_price, available_rooms, eligible_reward_base, cancellation, departure_date, data_label) VALUES ('VT-018', 'San Juan Old Town', 'Puerto Rico', 3290, 7, 2632.0, 'Hotel becomes nonrefundable 14 days before departure; flight fare rules apply.', '2027-04-10', 'Synthetic demo offer');
