Name:		mwiede-jsch
Version:	0.2.16
Release:	1
Summary:	Fork of JSch used by Gradle
Group:		Development/Java
License:	BSD-3-Clause AND ISC
URL:		https://github.com/mwiede/jsch
# Tag jsch-0.2.16. The archive has no prebuilt jars or native libraries.
Source0:	https://github.com/mwiede/jsch/archive/refs/tags/jsch-%{version}.tar.gz#/mwiede-jsch-%{version}.tar.gz

BuildArch:	noarch
BuildRequires:	java-current-devel
BuildRequires:	sysjar
BuildRequires:	mvn(org.bouncycastle:bcprov-jdk18on)
BuildRequires:	mvn(org.apache.logging.log4j:log4j-api)
BuildRequires:	mvn(org.slf4j:slf4j-api) >= 2.0.17
BuildRequires:	mvn(net.java.dev.jna:jna)
BuildRequires:	mvn(net.java.dev.jna:jna-platform)
BuildRequires:	mvn(com.kohlschutter.junixsocket:junixsocket-common)

%description
com.github.mwiede:jsch %{version} is the SSH library Gradle 9.9.1 pins.
This is not com.jcraft:jsch. Optional integrations (Bouncy Castle, JNA,
junixsocket, SLF4J, and Log4j) are compiled in and stay optional.
The jar root is Java 8. Newer copies of JavaVersion, XDH, EdDSA, and
UnixDomainSocketFactory live under META-INF/versions.

%prep
%autosetup -n jsch-jsch-%{version} -p1
find . \( -name '*.jar' -o -name '*.class' -o -name '*.so' -o -name '*.node' -o -name '*.wasm' \) -delete

%build
mkdir -p gen/com/jcraft/jsch
sed 's|${versionWithoutMinus}|%{version}|' \
	src/main/java-templates/com/jcraft/jsch/Version.java \
	> gen/com/jcraft/jsch/Version.java
if grep -F '${' gen/com/jcraft/jsch/Version.java; then
	echo "Version.java still has an unresolved token" >&2
	exit 1
fi

find src/main/java -name '*.java' > sources.list
echo gen/com/jcraft/jsch/Version.java >> sources.list
test "$(wc -l < sources.list)" -eq 273

# slf4j 2.0.17 ships the API at %{_javadir}/slf4j-api.jar.
# The 1.7 layout %{_javadir}/slf4j/slf4j-api.jar is a different package.
CP="%{_javadir}/bcprov-jdk18on.jar:%{_javadir}/log4j-api.jar:%{_javadir}/slf4j-api.jar:%{_javadir}/jna.jar:%{_javadir}/jna-platform.jar:%{_javadir}/junixsocket-common.jar"
mkdir -p classes
javac --release 8 -encoding UTF-8 -cp "$CP" -d classes @sources.list

overlay() {
	rel="$1"
	shift
	dest="v${rel}"
	rm -rf "$dest"
	mkdir -p "$dest"
	javac --release "$rel" -encoding UTF-8 -cp "classes:$CP" -d "$dest" "$@"
	mkdir -p "classes/META-INF/versions/${rel}"
	/bin/cp -a "$dest"/. "classes/META-INF/versions/${rel}/"
}
overlay 9 \
	src/main/java9/com/jcraft/jsch/JplLogger.java \
	src/main/java9/com/jcraft/jsch/JavaVersion.java
overlay 10 src/main/java10/com/jcraft/jsch/JavaVersion.java
overlay 11 src/main/java11/com/jcraft/jsch/jce/XDH.java
overlay 15 \
	src/main/java15/com/jcraft/jsch/jce/SignatureEdDSA.java \
	src/main/java15/com/jcraft/jsch/jce/SignatureEd448.java \
	src/main/java15/com/jcraft/jsch/jce/SignatureEd25519.java \
	src/main/java15/com/jcraft/jsch/jce/KeyPairGenEdDSA.java
overlay 16 src/main/java16/com/jcraft/jsch/UnixDomainSocketFactory.java

cat > manifest.txt << 'END'
Manifest-Version: 1.0
Multi-Release: true
END
jar cfm mwiede-jsch.jar manifest.txt -C classes .
jar i mwiede-jsch.jar
jar tf mwiede-jsch.jar | grep -E 'module-info|\.(java|jar|so|node|wasm)$' && exit 1 || true
javap -v -classpath mwiede-jsch.jar com.jcraft.jsch.JSch | grep -q 'major version: 52'

cat > mwiede-jsch.pom << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.github.mwiede</groupId>
  <artifactId>jsch</artifactId>
  <version>0.2.16</version>
  <name>mwiede-jsch</name>
  <description>Fork of JSch used by Gradle</description>
  <licenses>
    <license>
      <name>BSD-3-Clause</name>
    </license>
  </licenses>
</project>
EOF

%install
sysjar install --buildroot %{buildroot} \
	--artifact mwiede-jsch.pom:mwiede-jsch.jar \
	--file-name mwiede-jsch \
	--filelist .mfiles

%check
mkdir -p check
cat > check/Smoke.java << 'END'
import com.jcraft.jsch.JSch;
public class Smoke {
	public static void main(String[] args) {
		JSch jsch = new JSch();
		System.out.println("jsch_ok " + JSch.VERSION + " " + (jsch.getIdentityRepository() != null));
	}
}
END
JAR=%{buildroot}%{_javadir}/mwiede-jsch.jar
test -f "$JAR"
javac --release 8 -encoding UTF-8 -cp "$JAR" -d check check/Smoke.java
java -cp "check:$JAR" Smoke > check/out.txt
cat check/out.txt
grep -F -q 'jsch_ok 0.2.16 true' check/out.txt

%files -f .mfiles
%doc LICENSE.txt LICENSE.jBCrypt.txt LICENSE.JZlib.txt
