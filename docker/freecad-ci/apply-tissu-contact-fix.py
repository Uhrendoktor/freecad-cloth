    bvh_header_text = bvh_header.read_text(encoding="utf-8")
    private_anchor = """private:
    int buildRecursive(std::vector<Triangle>& tempTriangles,
                       const std::vector<Eigen::Vector3d>& vertices, int start,
                       int end);"""
    if bvh_header_text.count(private_anchor) != 1:
        raise RuntimeError("BVH private anchor mismatch")
    bvh_header_text = bvh_header_text.replace(
        private_anchor,
        """private:
    friend class MeshCollider;
    void query(const Eigen::AlignedBox3d& box,
               std::vector<int>& outTriangles) const;

    int buildRecursive(std::vector<Triangle>& tempTriangles,
                       const std::vector<Eigen::Vector3d>& vertices, int start,
                       int end);""",
        1,
    )
    recursive_anchor = "    void queryRecursive(int nodeIdx, const Eigen::Vector3d& point,"
    if bvh_header_text.count(recursive_anchor) != 1:
        raise RuntimeError("BVH box query helper declaration anchor mismatch")
    recursive_pos = bvh_header_text.index(recursive_anchor)
    line_start = bvh_header_text.rfind("\n", 0, recursive_pos) + 1
    bvh_header_text = (
        bvh_header_text[:line_start]
        + "    void queryBoxRecursive(int nodeIdx, const Eigen::AlignedBox3d& box,\n"
        + "                           std::vector<int>& outTriangles) const;\n"
        + bvh_header_text[line_start:]
    )
    bvh_header.write_text(bvh_header_text, encoding="utf-8")

