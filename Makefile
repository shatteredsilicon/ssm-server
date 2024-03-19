BUILDDIR	?= /tmp/ssmbuild
VERSION		?= 9.4.1
RELEASE		?= 1

ifeq (0, $(shell hash dpkg 2>/dev/null; echo $$?))
ARCH	:= $(shell dpkg --print-architecture)
else
ARCH	:= $(shell rpm --eval "%{_arch}")
endif

TARBALL_FILE	:= $(BUILDDIR)/tarballs/ssm-server-$(VERSION)-$(RELEASE).tar.gz
SRPM_FILE		:= $(BUILDDIR)/results/SRPMS/ssm-server-$(VERSION)-$(RELEASE).src.rpm
RPM_FILE		:= $(BUILDDIR)/results/RPMS/ssm-server-$(VERSION)-$(RELEASE).$(ARCH).rpm

.PHONY: all
all: srpm rpm

$(TARBALL_FILE):
	mkdir -vp $(shell dirname $(TARBALL_FILE))

	cd password-page; \
		npm install --no-audit --ignore-scripts --legacy-peer-deps

	tar -czf $(TARBALL_FILE) -C $(shell dirname $(CURDIR)) --transform s/^$(shell basename $(CURDIR))/ssm-server/ $(shell basename $(CURDIR))

.PHONY: srpm
srpm: $(SRPM_FILE)

$(SRPM_FILE): $(TARBALL_FILE)
	mkdir -vp $(BUILDDIR)/rpmbuild/{SOURCES,SPECS,BUILD,SRPMS,RPMS}
	mkdir -vp $(shell dirname $(SRPM_FILE))

	cp ssm-server.spec $(BUILDDIR)/rpmbuild/SPECS/ssm-server.spec
	sed -i "s/%{_version}/$(VERSION)/g" "$(BUILDDIR)/rpmbuild/SPECS/ssm-server.spec"
	sed -i "s/%{_release}/$(RELEASE)/g" "$(BUILDDIR)/rpmbuild/SPECS/ssm-server.spec"
	cp $(TARBALL_FILE) $(BUILDDIR)/rpmbuild/SOURCES/
	rpmbuild -bs --define "debug_package %{nil}" --define "_topdir $(BUILDDIR)/rpmbuild" $(BUILDDIR)/rpmbuild/SPECS/ssm-server.spec
	mv $(BUILDDIR)/rpmbuild/SRPMS/$(shell basename $(SRPM_FILE)) $(SRPM_FILE)

.PHONY: rpm
rpm: $(RPM_FILE)

$(RPM_FILE): $(SRPM_FILE)
	mkdir -vp $(BUILDDIR)/mock $(shell dirname $(RPM_FILE))
	mock -r ssm-9-$$(rpm --eval "%{_arch}") --resultdir $(BUILDDIR)/mock --rebuild $(SRPM_FILE)
	mv $(BUILDDIR)/mock/$(shell basename $(RPM_FILE)) $(RPM_FILE)

.PHONY: clean
clean:
	rm -rf $(BUILDDIR)/{tarballs,rpmbuild,mock,results}
