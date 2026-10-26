CREATE TABLE pricing_config (
	id UUID NOT NULL,
	config JSON NOT NULL,
	updated_by_name VARCHAR,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
);
-- statement-split
CREATE TABLE users (
	id UUID NOT NULL,
	email VARCHAR NOT NULL,
	name VARCHAR,
	role VARCHAR NOT NULL,
	onboarding_completed BOOLEAN NOT NULL,
	password_hash VARCHAR NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
);
-- statement-split
CREATE TABLE estimates (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	created_by_name VARCHAR,
	updated_by_name VARCHAR,
	deleted_at TIMESTAMP WITH TIME ZONE,
	type VARCHAR NOT NULL,
	source_estimate_id UUID,
	branch_state JSON,
	cover_image_id VARCHAR,
	status VARCHAR NOT NULL,
	title VARCHAR,
	room_name VARCHAR,
	wall_name VARCHAR,
	client_name VARCHAR,
	project_name VARCHAR,
	prepared_by VARCHAR,
	estimate_date DATE,
	description TEXT,
	notes TEXT,
	wall_width_ft NUMERIC(10, 2),
	wall_height_ft NUMERIC(10, 2),
	square_footage NUMERIC(10, 2),
	subtotal NUMERIC(12, 2) NOT NULL,
	final_total NUMERIC(12, 2) NOT NULL,
	markup_pct NUMERIC(6, 2),
	discount_pct NUMERIC(6, 2),
	manual_override BOOLEAN NOT NULL,
	pdf_layout JSON,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (source_estimate_id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
	FOREIGN KEY(source_estimate_id) REFERENCES estimates (id) ON DELETE CASCADE
);
-- statement-split
CREATE TABLE estimate_zones (
	id UUID NOT NULL,
	estimate_id UUID NOT NULL,
	sort_order INTEGER NOT NULL,
	zone_type VARCHAR NOT NULL,
	label VARCHAR NOT NULL,
	room_name VARCHAR,
	wall_name VARCHAR,
	wall_width_ft NUMERIC(10, 2),
	wall_height_ft NUMERIC(10, 2),
	square_footage NUMERIC(10, 2),
	linear_footage NUMERIC(10, 2),
	notes TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(estimate_id) REFERENCES estimates (id) ON DELETE CASCADE
);
-- statement-split
CREATE TABLE pdf_files (
	id UUID NOT NULL,
	estimate_id UUID NOT NULL,
	file_path VARCHAR NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(estimate_id) REFERENCES estimates (id) ON DELETE CASCADE
);
-- statement-split
CREATE TABLE voice_files (
	id UUID NOT NULL,
	estimate_id UUID NOT NULL,
	file_path VARCHAR NOT NULL,
	transcript TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(estimate_id) REFERENCES estimates (id) ON DELETE CASCADE
);
-- statement-split
CREATE TABLE estimate_images (
	id UUID NOT NULL,
	estimate_id UUID NOT NULL,
	zone_id UUID,
	slot INTEGER NOT NULL,
	file_path VARCHAR NOT NULL,
	original_name VARCHAR,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(estimate_id) REFERENCES estimates (id) ON DELETE CASCADE,
	FOREIGN KEY(zone_id) REFERENCES estimate_zones (id) ON DELETE CASCADE
);
-- statement-split
CREATE TABLE line_items (
	id UUID NOT NULL,
	estimate_id UUID NOT NULL,
	zone_id UUID,
	section VARCHAR,
	sort_order INTEGER NOT NULL,
	name VARCHAR NOT NULL,
	description TEXT,
	calc_type VARCHAR NOT NULL,
	quantity NUMERIC(10, 2),
	unit VARCHAR,
	unit_price NUMERIC(12, 2),
	original_unit_price NUMERIC(12, 2),
	total_price NUMERIC(12, 2) NOT NULL,
	is_tbd BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(estimate_id) REFERENCES estimates (id) ON DELETE CASCADE,
	FOREIGN KEY(zone_id) REFERENCES estimate_zones (id) ON DELETE CASCADE
);
-- statement-split
CREATE UNIQUE INDEX ix_users_email ON users (email);
-- statement-split
CREATE INDEX ix_estimates_deleted_at ON estimates (deleted_at);
-- statement-split
CREATE INDEX ix_estimates_user_id ON estimates (user_id);
-- statement-split
CREATE INDEX ix_estimate_zones_estimate_id ON estimate_zones (estimate_id);
-- statement-split
CREATE INDEX ix_estimate_images_zone_id ON estimate_images (zone_id);
-- statement-split
CREATE INDEX ix_line_items_estimate_id ON line_items (estimate_id);
-- statement-split
CREATE INDEX ix_line_items_zone_id ON line_items (zone_id);
