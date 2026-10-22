"""No shipped class points into a package that no shipped jar provides.

``scripts/jar_exclusions.txt`` removes jars from the wheel. Nothing used to check
that what remains still has what it calls. Three times that gap shipped a
working-looking wheel with a broken feature:

* Jackson was excluded as "embedded-unused" (2026-07-05), then server mode came
  back (2026-08-01) and ``GET /api/v1/openapi.json`` answered 500
  ``NoClassDefFoundError``.
* snappy-java was excluded the same day, and the Prometheus remote read and
  write routes, and every snappy-compressed request body, answered 500.
* commons-math3 was excluded while jvector's ``ScoreTracker$TwoPhaseTracker``
  still refers to it.

An exclusion run (a quarantine plus the test suite) cannot find these, because
the suite only exercises the paths the suite has. This test reads the class files
instead. For every class in every shipped jar it takes the classes the constant
pool names and requires that the package is provided by a shipped jar or by the
JDK. A package that nothing provides must be in ``ALLOWED_DANGLING`` with a
reason.

The same gap exists one level down: the bundled JRE is a jlink image without the
modules in ``scripts/jre_module_exclusions.txt`` (``java.desktop``, ``jdk.jfr``,
``java.compiler``). A shipped class that names a package of one of those modules
fails with ``NoClassDefFoundError`` when its code path runs, and jdeps cannot say
so, because the build removes those modules from jdeps's answer. The second half of
this file reads the class files against the packages the running JVM provides.

If this test fails after you excluded a jar, the jar is needed: take it off
``jar_exclusions.txt``. If it fails after an engine or dependency update, a new
class refers to a library the wheel does not ship: decide whether the code path
is reachable, and either ship the jar or add an entry below that says why not.
"""

import os
import shutil
import struct
import zipfile

import pytest
from arcadedb_embedded.jvm import get_jar_path

# Packages the JDK provides. The first test checks the jars only. The bundled JRE
# is a jlink image, and the modules it lacks on purpose are checked by the tests
# at the end of this file (REMOVED_MODULE_PACKAGES); any other module that is
# missing is caught by jdeps at build time, which derives the module list from
# these same jars.
JDK_PREFIXES = (
    "java/",
    "javax/",
    "jdk/",
    "sun/",
    "com/sun/",
    "org/w3c/",
    "org/xml/",
    "org/ietf/",
    "org/omg/",
)

# (referencing jar name prefix, package prefix, why a missing package is fine).
# A reference is excused only when the referencing jar AND the package match, so
# a new dangling reference from the engine itself is never excused by an entry
# written for a third-party library.
ALLOWED_DANGLING = (
    (
        "micrometer-",
        "",
        "Micrometer binders for libraries (Jetty, Kafka, Hibernate, Netty, Log4j, "
        "OkHttp, jOOQ, ...) that are loaded only when the application uses that "
        "library. ArcadeDB's server registers none of them.",
    ),
    (
        "jboss-logging",
        "org/apache/log4j",
        "Optional logging backend; the wheel logs through java.util.logging.",
    ),
    (
        "jboss-logging",
        "org/apache/logging/log4j",
        "Optional logging backend; the wheel logs through java.util.logging.",
    ),
    (
        "jboss-logging",
        "org/jboss/logmanager",
        "Optional logging backend; the wheel logs through java.util.logging.",
    ),
    (
        "xnio-",
        "org/jboss/logging/annotations",
        "Annotations of the JBoss message-logger annotation processor, "
        "needed at compile time only.",
    ),
    (
        "xnio-",
        "org/osgi/framework",
        "OSGi bundle activator, loaded only inside an OSGi container.",
    ),
    (
        "snappy-java-",
        "org/osgi/framework",
        "OSGi bundle activator, loaded only inside an OSGi container.",
    ),
    (
        "smallrye-common-annotation-",
        "jakarta/enterprise/util",
        "CDI types for a CDI container; the server is not one.",
    ),
    (
        "spatial4j-",
        "org/noggit",
        "Optional GeoJSON reader; ArcadeDB's geo functions do not use it.",
    ),
    (
        "arcadedb-console-",
        "org/jline",
        "The interactive console is a command-line tool that is not started from "
        "Python; jline is in jar_exclusions.txt for that reason.",
    ),
)


def _class_references(data):
    """The internal names of the classes a class file's constant pool names.

    Parses the constant pool only (JVMS 4.4): the table sits first in the file
    and its Class entries (tag 7) are every class the code refers to by name.
    """
    count = struct.unpack_from(">H", data, 8)[0]
    pos = 10
    utf8 = {}
    class_indexes = []
    index = 1
    while index < count:
        tag = data[pos]
        if tag == 1:
            length = struct.unpack_from(">H", data, pos + 1)[0]
            utf8[index] = data[pos + 3 : pos + 3 + length]
            pos += 3 + length
        elif tag == 7:
            class_indexes.append(struct.unpack_from(">H", data, pos + 1)[0])
            pos += 3
        elif tag in (8, 16, 19, 20):  # String, MethodType, Module, Package
            pos += 3
        elif tag in (
            3,
            4,
            9,
            10,
            11,
            12,
            17,
            18,
        ):  # int, float, refs, NameAndType, dynamic
            pos += 5
        elif tag == 15:  # MethodHandle
            pos += 4
        elif tag in (5, 6):  # long, double take two slots
            pos += 9
            index += 1
        else:
            raise ValueError(f"unknown constant pool tag {tag}")
        index += 1
    return [utf8[i].decode("utf-8", "replace") for i in class_indexes if i in utf8]


def _package_of(class_name):
    """The package of a Class entry, which is a class name or an array descriptor."""
    name = class_name.lstrip("[")
    if name.startswith("L") and name.endswith(";"):
        name = name[1:-1]
    return name.rsplit("/", 1)[0] if "/" in name else ""


def _scan(jar_dir):
    """Return ``{(jar name, package): example class}`` for every dangling package."""
    jar_names = sorted(n for n in os.listdir(jar_dir) if n.endswith(".jar"))
    provided = set()
    references = {}
    for jar in jar_names:
        with zipfile.ZipFile(os.path.join(jar_dir, jar)) as archive:
            classes = [
                n
                for n in archive.namelist()
                if n.endswith(".class") and not n.startswith("META-INF/")
            ]
            for name in classes:
                provided.add(name.rsplit("/", 1)[0] if "/" in name else "")
            for name in classes:
                for ref in _class_references(archive.read(name)):
                    package = _package_of(ref)
                    if package:
                        references.setdefault((jar, package), name)
    return {
        key: example
        for key, example in references.items()
        if key[1] not in provided and not key[1].startswith(JDK_PREFIXES)
    }


def _is_allowed(jar, package):
    return any(
        jar.startswith(jar_prefix) and package.startswith(package_prefix)
        for jar_prefix, package_prefix, _ in ALLOWED_DANGLING
    )


def test_every_class_reference_resolves_to_a_shipped_jar():
    """No class refers to a package that only an excluded jar provides."""
    dangling = _scan(get_jar_path())
    unexplained = sorted(
        (jar, package, example)
        for (jar, package), example in dangling.items()
        if not _is_allowed(jar, package)
    )
    assert not unexplained, (
        "classes in the wheel refer to packages no shipped jar provides, so the "
        "code path that uses them fails with NoClassDefFoundError:\n"
        + "\n".join(
            f"  {package.replace('/', '.')}  (from {jar}, e.g. {example})"
            for jar, package, example in unexplained
        )
        + "\nShip the jar that provides it (remove it from scripts/jar_exclusions.txt),"
        " or, when the code path cannot be reached from the bindings, add an entry"
        " with a reason to ALLOWED_DANGLING in this file."
    )


def test_scanner_reports_a_package_whose_jar_is_missing(tmp_path):
    """The scan reports a reference whose provider is absent, so a pass means something.

    A directory holding only the jvector jar leaves its dependencies (agrona,
    commons-math3, slf4j, ...) unprovided, and the scan must say so.
    """
    jar_dir = get_jar_path()
    jvector = [n for n in os.listdir(jar_dir) if n.startswith("jvector-")]
    assert jvector, "jvector jar missing from the wheel"
    shutil.copy(os.path.join(jar_dir, jvector[0]), tmp_path / jvector[0])
    packages = {package for (_, package) in _scan(str(tmp_path))}
    assert "org/agrona/collections" in packages
    assert not any(p.startswith("io/github/jbellis/jvector") for p in packages)


def test_class_reference_parser_reads_a_real_class():
    """The constant-pool parser returns the classes a known class names."""
    jar_dir = get_jar_path()
    engine = [n for n in os.listdir(jar_dir) if n.startswith("arcadedb-engine-")][0]
    with zipfile.ZipFile(os.path.join(jar_dir, engine)) as archive:
        refs = _class_references(archive.read("com/arcadedb/Constants.class"))
    assert "com/arcadedb/Constants" in refs
    assert "java/lang/String" in refs


def test_polyglot_engine_is_off_while_no_graalvm_language_ships(tmp_path):
    """The engine is off by default because the wheel carries no language for it.

    GraalJS (js-language, truffle, icu4j, regex) is in jar_exclusions.txt, so a
    polyglot engine would start with nothing to register and log "no languages
    found" at the first SQL command, and ``DEFINE FUNCTION ... LANGUAGE js``
    cannot work either way. If a language jar is ever shipped, this test stops
    asserting either half.
    """
    import arcadedb_embedded as arcadedb
    import jpype
    from arcadedb_embedded.exceptions import ArcadeDBError

    service = (
        "META-INF/services/com.oracle.truffle.api.provider.TruffleLanguageProvider"
    )
    jar_dir = get_jar_path()
    language_shipped = False
    for name in os.listdir(jar_dir):
        if name.endswith(".jar"):
            with zipfile.ZipFile(os.path.join(jar_dir, name)) as archive:
                language_shipped = language_shipped or service in archive.namelist()

    with arcadedb.create_database(str(tmp_path / "poly")) as db:
        configuration = jpype.JClass("com.arcadedb.GlobalConfiguration")
        enabled = bool(configuration.POLYGLOT_ENGINE_ENABLED.getValueAsBoolean())
        assert language_shipped or not enabled, (
            "the polyglot engine is enabled but no GraalVM language is in the wheel; "
            "start_jvm() should default -Darcadedb.polyglotEngineEnabled=false"
        )
        if not language_shipped:
            with pytest.raises(ArcadeDBError):
                db.command(
                    "sql",
                    'DEFINE FUNCTION jsfn.add "return a + b;" PARAMETERS [a,b] LANGUAGE js',
                )


# The JDK modules that scripts/jre_module_exclusions.txt keeps out of the bundled
# runtime, with the packages each one provides in the full JDK. A package that is
# in this table and that the running JVM does not provide is "removed on purpose".
# java.datatransfer and java.prefs go with java.desktop, the only module that
# requires them.
REMOVED_MODULES = (
    "java.desktop",
    "java.datatransfer",
    "java.prefs",
    "jdk.jfr",
    "java.compiler",
)
REMOVED_MODULE_PACKAGES = (
    "java/awt",  # java.desktop, and java/awt/datatransfer of java.datatransfer
    "java/beans",
    "java/applet",
    "java/util/prefs",
    "javax/swing",
    "javax/imageio",
    "javax/sound",
    "javax/print",
    "javax/accessibility",
    "javax/tools",  # java.compiler
    "javax/lang/model",
    "javax/annotation/processing",
    "jdk/jfr",
    "sun/awt",
    "sun/java2d",
    "sun/swing",
    "com/sun/beans",
    "com/sun/java/swing",
)

# (referencing jar name prefix, package prefix, why the code path is unreachable).
# Same rule as ALLOWED_DANGLING: the entry excuses only that jar and that package.
# Every entry was checked by reading the callers in the shipped jars (2026-10-22):
# no class outside the named one refers to it.
ALLOWED_REMOVED_MODULE_USE = (
    (
        "jts-core-",
        "java/awt",
        "org.locationtech.jts.awt (AWT shape reader and writer for drawing) and "
        "util.TestBuilderProxy. ArcadeDB parses, indexes and tests geometries and "
        "never refers to the awt package, and no other JTS class does.",
    ),
    (
        "jackson-databind-",
        "java/beans",
        "ext.Java7SupportImpl (@ConstructorProperties and @Transient). Jackson "
        "loads it in a try block and works without that annotation support; "
        "test_jackson_and_yaml_work_without_java_beans runs it on this runtime.",
    ),
    (
        "snakeyaml-",
        "java/beans",
        "introspector.MethodProperty, the bean mapper of Yaml, Constructor and "
        "Representer. Nothing in the wheel creates a Yaml object: "
        "jackson-dataformat-yaml uses only the parser and the emitter.",
    ),
    (
        "commons-lang3-",
        "java/beans",
        "concurrent.AbstractCircuitBreaker (PropertyChangeSupport), which nothing "
        "in the wheel extends.",
    ),
    (
        "commons-math3-",
        "java/awt",
        "geometry.euclidean.twod.Line (AffineTransform), a 2-D geometry class. "
        "jvector refers to other commons-math3 classes only.",
    ),
    (
        "micrometer-core-",
        "java/beans",
        "binder.logging.Log4j2Metrics, bound only by an application that registers "
        "it; the wheel logs through java.util.logging and ships no Log4j2.",
    ),
    (
        "jakarta.xml.bind-api-",
        "java/beans",
        "javax.xml.bind.JAXB, a convenience class. swagger-core refers to the "
        "javax.xml.bind.annotation annotations only, which need no JDK module.",
    ),
    (
        "jakarta.activation-api-",
        "java/awt/datatransfer",
        "javax.activation.DataHandler and its content handlers (data flavors for "
        "JAXB attachments). No class outside the jar refers to javax.activation.",
    ),
    (
        "arcadedb-engine-",
        "jdk/jfr",
        "utility.JVMGCHistogramReporter (Flight Recorder allocation stream). No "
        "class, command or setting calls it; the JFR events of the JVM itself "
        "need no Java module.",
    ),
    (
        "agrona-",
        "javax/tools",
        "org.agrona.generation, agrona's code generator that compiles source at "
        "run time. Neither jvector nor the engine calls it.",
    ),
)


def _runtime_packages():
    """The packages of every module in the running JVM's boot layer, as ``a/b/c``."""
    import jpype
    from arcadedb_embedded.jvm import start_jvm

    start_jvm()
    modules = jpype.JClass("java.lang.ModuleLayer").boot().modules()
    return {
        str(package).replace(".", "/")
        for module in modules
        for package in module.getPackages()
    }


def _removed_module_references(jar_dir, runtime_packages):
    """Return ``{(jar, package): example class}`` for packages of removed modules.

    Unlike ``_scan`` this reads the multi-release classes under
    ``META-INF/versions/<n>`` for ``n`` up to the runtime's Java 25, as jdeps
    does with ``--multi-release 25``, because the JVM loads them.
    """
    found = {}
    for jar in sorted(n for n in os.listdir(jar_dir) if n.endswith(".jar")):
        with zipfile.ZipFile(os.path.join(jar_dir, jar)) as archive:
            for name in archive.namelist():
                if not name.endswith(".class"):
                    continue
                if name.startswith("META-INF/versions/"):
                    version, _, rest = name[len("META-INF/versions/") :].partition("/")
                    if not version.isdigit() or int(version) > 25:
                        continue
                    class_file = rest
                elif name.startswith("META-INF/"):
                    continue
                else:
                    class_file = name
                if class_file == "module-info.class":
                    continue
                for ref in _class_references(archive.read(name)):
                    package = _package_of(ref)
                    if package in runtime_packages:
                        continue
                    if any(
                        package == removed or package.startswith(removed + "/")
                        for removed in REMOVED_MODULE_PACKAGES
                    ):
                        found.setdefault((jar, package), class_file)
    return found


def _removed_module_use_is_allowed(jar, package):
    return any(
        jar.startswith(jar_prefix) and package.startswith(package_prefix)
        for jar_prefix, package_prefix, _ in ALLOWED_REMOVED_MODULE_USE
    )


def test_bundled_runtime_lacks_the_excluded_modules():
    """The runtime really is the trimmed one, so the closure test below means something."""
    import jpype
    from arcadedb_embedded.jvm import start_jvm

    start_jvm()
    layer = jpype.JClass("java.lang.ModuleLayer").boot()
    present = [m for m in REMOVED_MODULES if layer.findModule(m).isPresent()]
    assert not present, (
        f"the bundled JRE contains {present}, which scripts/jre_module_exclusions.txt "
        "keeps out; the wheel was built without that list"
    )


def test_no_shipped_class_needs_a_module_the_runtime_lacks():
    """Every class that names a removed module's package is on the allow list."""
    found = _removed_module_references(get_jar_path(), _runtime_packages())
    unexplained = sorted(
        (jar, package, example)
        for (jar, package), example in found.items()
        if not _removed_module_use_is_allowed(jar, package)
    )
    assert not unexplained, (
        "classes in the wheel refer to a package of a JDK module that the bundled "
        "JRE lacks (scripts/jre_module_exclusions.txt), so the code path that uses "
        "them fails with NoClassDefFoundError:\n"
        + "\n".join(
            f"  {package.replace('/', '.')}  (from {jar}, e.g. {example})"
            for jar, package, example in unexplained
        )
        + "\nKeep the module (remove it from jre_module_exclusions.txt), or, when the"
        " code path cannot be reached from the bindings, add an entry with a reason"
        " to ALLOWED_REMOVED_MODULE_USE in this file."
    )


def test_removed_module_scan_sees_the_known_references():
    """With no runtime packages the scan finds the references, so a pass means something."""
    found = _removed_module_references(get_jar_path(), set())
    seen = {(jar.split("-")[0], package) for jar, package in found}
    assert ("jackson", "java/beans") in seen
    assert ("jts", "java/awt/geom") in seen
    assert ("arcadedb", "jdk/jfr/consumer") in seen
    assert ("agrona", "javax/tools") in seen


def test_allowed_removed_module_entries_still_match_a_reference():
    """An entry that no class needs any more is dead text: remove it."""
    found = _removed_module_references(get_jar_path(), set())
    stale = [
        (jar_prefix, package_prefix)
        for jar_prefix, package_prefix, _ in ALLOWED_REMOVED_MODULE_USE
        if not any(
            jar.startswith(jar_prefix) and package.startswith(package_prefix)
            for jar, package in found
        )
    ]
    assert not stale, f"entries of ALLOWED_REMOVED_MODULE_USE match nothing: {stale}"


def test_jackson_and_yaml_work_without_java_beans(tmp_path):
    """Jackson and the YAML mapper run on this runtime, which has no java.beans.

    The allow list says jackson-databind's java.beans use is optional and that the
    YAML mapper does not touch snakeyaml's bean introspector. Run both.
    """
    import jpype
    from arcadedb_embedded.jvm import start_jvm

    start_jvm()
    mapper = jpype.JClass("com.fasterxml.jackson.databind.ObjectMapper")()
    tree = mapper.readTree('{"a":[1,2,{"b":"c"}],"d":null}')
    assert str(mapper.writeValueAsString(tree)) == '{"a":[1,2,{"b":"c"}],"d":null}'
    hash_map = jpype.JClass("java.util.LinkedHashMap")()
    hash_map.put("name", "arcade")
    hash_map.put("n", jpype.JClass("java.lang.Integer")(3))
    assert "arcade" in str(mapper.writeValueAsString(hash_map))

    yaml = jpype.JClass("com.fasterxml.jackson.dataformat.yaml.YAMLMapper")()
    text = str(yaml.writeValueAsString(hash_map))
    assert "name: " in text and "arcade" in text
    back = yaml.readTree(text)
    assert str(back.get("name").asText()) == "arcade"
