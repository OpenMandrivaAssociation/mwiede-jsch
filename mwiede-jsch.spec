Name:		mwiede-jsch
Version:	0.2.26
Release:	1
Summary:	Fork of JSch used by Gradle
Group:		Development/Java
License:	BSD-3-Clause AND ISC
URL:		https://github.com/mwiede/jsch
# Tag jsch-0.2.26. The archive has no prebuilt jars or native libraries.
# Gradle 9.9.1 strictly pins 0.2.16. Do not jump to the 2.x line.
Source0:	https://github.com/mwiede/jsch/archive/refs/tags/jsch-%{version}.tar.gz#/mwiede-jsch-%{version}.tar.gz
Source1:	https://github.com/mwiede/jsch/archive/refs/tags/jsch-0.2.16.tar.gz#/mwiede-jsch-0.2.16.tar.gz

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
com.github.mwiede:jsch %{version} is the SSH library Gradle uses.
Gradle 9.9.1 strictly pins 0.2.16, so that jar is installed beside
%{version}. This is not com.jcraft:jsch, and it is not the later 2.x
line. Optional integrations (Bouncy Castle, JNA, junixsocket, SLF4J,
and Log4j) are compiled in and stay optional. The jar root is Java 8.
Newer copies of JavaVersion, XDH, EdDSA, and UnixDomainSocketFactory
live under META-INF/versions. %{version} also carries the Java 24
ML-KEM key exchange there.

0.2.17 through %{version} add sntrup761 and ML-KEM hybrid key
exchange, prefer AES-GCM to AES-CTR, enforce DH group size, and fix
rekeying timeouts and the GSSAPI service name OID.

%prep
%autosetup -n jsch-jsch-%{version} -p1
%setup -q -T -D -a 1 -n jsch-jsch-%{version}
find . \( -name '*.jar' -o -name '*.class' -o -name '*.so' -o -name '*.node' -o -name '*.wasm' \) -delete
# Bouncy Castle 1.86 moved ML-KEM out of org.bouncycastle.pqc.crypto.mlkem.
mlkem_sources=$(find . -path '*/com/jcraft/jsch/bc/MLKEM*.java' | sort)
if [ -n "$mlkem_sources" ]; then
	sed -i \
		-e 's|org\.bouncycastle\.pqc\.crypto\.mlkem\.MLKEMExtractor|org.bouncycastle.crypto.kems.MLKEMExtractor|' \
		-e 's|org\.bouncycastle\.pqc\.crypto\.mlkem\.MLKEMKeyPairGenerator|org.bouncycastle.crypto.generators.MLKEMKeyPairGenerator|' \
		-e 's|org\.bouncycastle\.pqc\.crypto\.mlkem\.MLKEMKeyGenerationParameters|org.bouncycastle.crypto.params.MLKEMKeyGenerationParameters|' \
		-e 's|org\.bouncycastle\.pqc\.crypto\.mlkem\.MLKEMPrivateKeyParameters|org.bouncycastle.crypto.params.MLKEMPrivateKeyParameters|' \
		-e 's|org\.bouncycastle\.pqc\.crypto\.mlkem\.MLKEMPublicKeyParameters|org.bouncycastle.crypto.params.MLKEMPublicKeyParameters|' \
		-e 's|org\.bouncycastle\.pqc\.crypto\.mlkem\.MLKEMParameters|org.bouncycastle.crypto.params.MLKEMParameters|' \
		$mlkem_sources
	if grep -F 'org.bouncycastle.pqc.crypto.mlkem' $mlkem_sources; then
		echo "ML-KEM import was not rewritten" >&2
		exit 1
	fi
fi

%build
set -eo pipefail
export JAVA_HOME=%{_jvmdir}/java-openjdk
export PATH=$JAVA_HOME/bin:$PATH
# slf4j 2.0.17 ships the API at %{_javadir}/slf4j-api.jar.
# The 1.7 layout %{_javadir}/slf4j/slf4j-api.jar is a different package.
CP="%{_javadir}/bcprov-jdk18on.jar:%{_javadir}/log4j-api.jar:%{_javadir}/slf4j-api.jar:%{_javadir}/jna.jar:%{_javadir}/jna-platform.jar:%{_javadir}/junixsocket-common.jar"

compile_one() {
	root="$1"
	ver="$2"
	count="$3"
	expect="$4"
	(
		cd "$root"
		set -eo pipefail
		mkdir -p gen/com/jcraft/jsch out
		sed 's|${versionWithoutMinus}|'"$ver"'|' \
			src/main/java-templates/com/jcraft/jsch/Version.java \
			> gen/com/jcraft/jsch/Version.java
		if grep -F '${' gen/com/jcraft/jsch/Version.java; then
			echo "Version.java still has an unresolved token" >&2
			exit 1
		fi
		find src/main/java -name '*.java' > sources.list
		echo gen/com/jcraft/jsch/Version.java >> sources.list
		test "$(wc -l < sources.list)" -eq "$count"
		mkdir -p classes
		javac --release 8 -encoding UTF-8 -cp "$CP" -d classes @sources.list
		rels=""
		for dir in src/main/java[0-9]*; do
			if [ ! -d "$dir" ]; then
				continue
			fi
			rel=$(printf '%s' "$dir" | sed 's|.*java||')
			rels="$rels $rel"
			dest="v$rel"
			/bin/rm -rf "$dest"
			mkdir -p "$dest"
			find "$dir" -name '*.java' ! -name module-info.java > "overlay-$rel.list"
			test -s "overlay-$rel.list"
			javac --release "$rel" -encoding UTF-8 -cp "classes:$CP" -d "$dest" @"overlay-$rel.list"
			mkdir -p "classes/META-INF/versions/$rel"
			/bin/cp -a "$dest"/. "classes/META-INF/versions/$rel/"
		done
		got=$(printf '%s\n' $rels | sort -n | tr '\n' ' ' | sed 's/ $//')
		if [ "$got" != "$expect" ]; then
			echo "overlays [$got] want [$expect]" >&2
			exit 1
		fi
		printf 'Manifest-Version: 1.0\nMulti-Release: true\n' > out/manifest.txt
		jar cfm out/mwiede-jsch.jar out/manifest.txt -C classes .
		jar i out/mwiede-jsch.jar
		jar tf out/mwiede-jsch.jar | grep -E 'module-info|\.(java|jar|so|node|wasm)$' && exit 1 || true
		javap -v -classpath out/mwiede-jsch.jar com.jcraft.jsch.JSch | grep -q 'major version: 52'
		cat > out/mwiede-jsch.pom << EOF
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.github.mwiede</groupId>
  <artifactId>jsch</artifactId>
  <version>$ver</version>
  <name>mwiede-jsch</name>
  <description>Fork of JSch used by Gradle</description>
  <licenses>
    <license>
      <name>BSD-3-Clause</name>
    </license>
  </licenses>
</project>
EOF
		grep -F -q "<version>$ver</version>" out/mwiede-jsch.pom
	)
}

compile_one . %{version} 284 "9 10 11 15 16 24"
compile_one jsch-jsch-0.2.16 0.2.16 273 "9 10 11 15 16"

%install
set -eo pipefail
sysjar install --buildroot %{buildroot} \
	--artifact jsch-jsch-0.2.16/out/mwiede-jsch.pom:jsch-jsch-0.2.16/out/mwiede-jsch.jar \
	--file-name mwiede-jsch-0.2.16 \
	--filelist .mfiles016
/bin/mv %{buildroot}/usr/share/sysjar/index/com.github.mwiede/jsch.sysjar \
	%{buildroot}/usr/share/sysjar/index/com.github.mwiede/jsch-0.2.16.sysjar
sed -i 's|/usr/share/sysjar/index/com.github.mwiede/jsch\.sysjar|/usr/share/sysjar/index/com.github.mwiede/jsch-0.2.16.sysjar|' .mfiles016
sysjar install --buildroot %{buildroot} \
	--artifact out/mwiede-jsch.pom:out/mwiede-jsch.jar \
	--file-name mwiede-jsch \
	--filelist .mfiles026
awk '!seen[$0]++' .mfiles016 .mfiles026 > .mfiles

%check
set -eo pipefail
export JAVA_HOME=%{_jvmdir}/java-openjdk
export PATH=$JAVA_HOME/bin:$PATH
jar tf %{buildroot}%{_javadir}/mwiede-jsch.jar | grep -F 'META-INF/versions/24/com/jcraft/jsch/jce/MLKEM768.class'
if jar tf %{buildroot}%{_javadir}/mwiede-jsch-0.2.16.jar | grep -F MLKEM; then
	echo "0.2.16 jar contains ML-KEM" >&2
	exit 1
fi
smoke_one() {
	label="$1"
	ver="$2"
	jarfile="$3"
	mkdir -p "check-$label"
	cat > "check-$label/Smoke.java" << 'END'
import com.jcraft.jsch.JSch;
public class Smoke {
	public static void main(String[] args) {
		JSch jsch = new JSch();
		System.out.println(args[0] + " " + JSch.VERSION + " " + (jsch.getIdentityRepository() != null));
	}
}
END
	javac --release 8 -encoding UTF-8 -cp "$jarfile" -d "check-$label" "check-$label/Smoke.java"
	java -cp "check-$label:$jarfile" Smoke "$label" > "check-$label/out.txt"
	cat "check-$label/out.txt"
	grep -F -q "$label $ver true" "check-$label/out.txt"
}
smoke_one jsch026_ok %{version} %{buildroot}%{_javadir}/mwiede-jsch.jar
smoke_one jsch016_ok 0.2.16 %{buildroot}%{_javadir}/mwiede-jsch-0.2.16.jar

%files -f .mfiles
%doc LICENSE.txt LICENSE.jBCrypt.txt LICENSE.JZlib.txt
