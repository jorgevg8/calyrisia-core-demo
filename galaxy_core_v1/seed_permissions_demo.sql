-- ============================================================
-- GALAXY AUTOMATIONS
-- GALAXY BUSINESS AUTOPILOT
-- PASO 16 - DEMO PERMISSIONS
-- Business: Galaxy Demo Store
-- ============================================================

-- Lecturas permitidas para el sistema Galaxy.
INSERT INTO permissions (
    business_id,
    name,
    description,
    subject_type,
    resource_type,
    action_type,
    effect,
    requires_approval,
    priority,
    enabled
)
SELECT
    '3063ebc7-fdfe-4959-9e92-5b9f583075bb',
    x.name,
    x.description,
    'system',
    x.resource_type,
    'read',
    'allow',
    FALSE,
    100,
    TRUE
FROM (
    VALUES
        ('Galaxy read business profile', 'Galaxy can read the business profile.', 'business_profile'),
        ('Galaxy read customer', 'Galaxy can read customer information.', 'customer'),
        ('Galaxy read product', 'Galaxy can read product information.', 'product'),
        ('Galaxy read inventory', 'Galaxy can read inventory information.', 'inventory'),
        ('Galaxy read order', 'Galaxy can read order information.', 'order')
) AS x(name, description, resource_type)
WHERE NOT EXISTS (
    SELECT 1
    FROM permissions p
    WHERE p.business_id = '3063ebc7-fdfe-4959-9e92-5b9f583075bb'
      AND p.subject_type = 'system'
      AND p.resource_type = x.resource_type
      AND p.action_type = 'read'
      AND p.effect = 'allow'
);

-- Crear pedidos: permitido, pero siempre requiere aprobación en este MVP.
INSERT INTO permissions (
    business_id,
    name,
    description,
    subject_type,
    resource_type,
    action_type,
    effect,
    requires_approval,
    priority,
    enabled
)
SELECT
    '3063ebc7-fdfe-4959-9e92-5b9f583075bb',
    'Galaxy create order with approval',
    'Galaxy may prepare an order, but a human must approve it before execution.',
    'system',
    'order',
    'create',
    'allow',
    TRUE,
    100,
    TRUE
WHERE NOT EXISTS (
    SELECT 1
    FROM permissions p
    WHERE p.business_id = '3063ebc7-fdfe-4959-9e92-5b9f583075bb'
      AND p.subject_type = 'system'
      AND p.resource_type = 'order'
      AND p.action_type = 'create'
      AND p.effect = 'allow'
);

-- Ajuste de inventario: bloqueado para Galaxy en esta fase.
INSERT INTO permissions (
    business_id,
    name,
    description,
    subject_type,
    resource_type,
    action_type,
    effect,
    requires_approval,
    priority,
    enabled
)
SELECT
    '3063ebc7-fdfe-4959-9e92-5b9f583075bb',
    'Block autonomous inventory update',
    'Inventory updates remain blocked until the approval/execution workflow is fully implemented.',
    'system',
    'inventory',
    'update',
    'deny',
    FALSE,
    10,
    TRUE
WHERE NOT EXISTS (
    SELECT 1
    FROM permissions p
    WHERE p.business_id = '3063ebc7-fdfe-4959-9e92-5b9f583075bb'
      AND p.subject_type = 'system'
      AND p.resource_type = 'inventory'
      AND p.action_type = 'update'
      AND p.effect = 'deny'
);

SELECT
    name,
    subject_type,
    resource_type,
    action_type,
    effect,
    requires_approval,
    priority,
    enabled
FROM permissions
WHERE business_id = '3063ebc7-fdfe-4959-9e92-5b9f583075bb'
ORDER BY priority, resource_type, action_type;
