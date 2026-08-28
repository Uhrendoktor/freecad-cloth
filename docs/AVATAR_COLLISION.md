# Avatar and collision contract

The simulation layer accepts an avatar collision surface independently of garment data. A surface consists of vertices, triangles, a unit convention, and a semantic body region. The core contract requires valid triangle indices and a consistent right-handed Z-up coordinate convention.

Collision preparation should validate watertightness/self-intersection where the imported mesh permits it, remove degenerate triangles, and generate a simplified proxy for performance. No proprietary avatar is required: CI fixtures can use generated primitives such as a capsule or box surface.

Body measurements affect garment placement/scaling, but solver code should receive already-normalized geometry. Region labels are diagnostic metadata rather than solver-specific types. Redistribution of sample humanoid assets is intentionally avoided.
