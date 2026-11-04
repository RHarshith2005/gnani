-- Synthetic demo data only. No real residents, vendors or prices.
-- One community of 120 households, 360 water cans a week, three simulated vendors.

insert into communities (id, name, households)
values ('green-residency', 'Green Residency', 120)
on conflict (id) do nothing;

insert into residents (id, community_id, flat_number, language, role)
select
  'res-' || g,
  'green-residency',
  'A-' || g,
  'kn-IN',
  'resident'
from generate_series(1, 120) as g
on conflict (id) do nothing;

-- Two named demo roles for /api/demo-login. Still synthetic, still no password.
insert into residents (id, community_id, flat_number, language, role)
values
  ('res-asha', 'green-residency', 'A-204', 'kn-IN', 'resident'),
  ('res-admin', 'green-residency', 'Office', 'en-IN', 'admin')
on conflict (id) do nothing;

insert into demand_requests
  (id, resident_id, community_id, product, qty, frequency, delivery_day, language, status)
select
  'dem-' || g,
  'res-' || g,
  'green-residency',
  'water can',
  3,
  'weekly',
  'Saturday',
  'kn-IN',
  'confirmed'
from generate_series(1, 120) as g
on conflict (id) do nothing;

-- Floors are held in the vendor agent, never in the database the browser reads.
insert into vendors (id, name, persona, product, free_delivery_qty, delivery_days, delivery_charge)
values
  ('vendor-stubborn', 'Sri Lakshmi Water Agency', 'stubborn', 'water can', 300, 2, 60),
  ('vendor-friendly', 'Bengaluru Aqua Distributors', 'friendly volume-hungry', 'water can', 240, 1, 0),
  ('vendor-cheap-slow', 'Cauvery Can Supply', 'cheap but slow', 'water can', 500, 3, 40)
on conflict (id) do nothing;
