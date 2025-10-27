#!/usr/bin/env python3
"""Test the installed JRE-bundled wheel"""
import os
import shutil
import tempfile

import arcadedb_embedded as arcadedb

print("🧪 Testing JRE-bundled wheel...")
print(f"📦 Package version: {arcadedb.__version__}")

# Check if JRE is bundled
package_dir = os.path.dirname(arcadedb.__file__)
jre_dir = os.path.join(package_dir, "jre")
print(f"📁 JRE bundled: {os.path.exists(jre_dir)}")

if os.path.exists(jre_dir):
    jre_size = sum(
        os.path.getsize(os.path.join(dirpath, filename))
        for dirpath, dirnames, filenames in os.walk(jre_dir)
        for filename in filenames
    ) / (
        1024 * 1024
    )  # MB
    print(f"   JRE size: {jre_size:.1f} MB")

# Test database operations
temp_dir = tempfile.mkdtemp()
db_path = os.path.join(temp_dir, "test_jre_bundle")

try:
    print("\n🎮 Testing database operations...")
    db = arcadedb.create_database(db_path)
    print("✅ Database created")

    with db.transaction():
        db.command("sql", "CREATE DOCUMENT TYPE JRETest")
        db.command("sql", "INSERT INTO JRETest SET name = 'bundled_jre', works = true")
    print("✅ Data inserted")

    result = list(db.query("sql", "SELECT FROM JRETest"))
    print(f"✅ Query returned: {len(result)} records")

    for r in result:
        name = r.get_property("name")
        works = r.get_property("works")
        print(f"   - {name}: works={works}")

    db.close()
    print("\n🎉 JRE-bundled wheel fully functional!")

finally:
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
