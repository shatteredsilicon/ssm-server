%define debug_package %{nil}

%global provider        github
%global provider_tld	com
%global project         shatteredsilicon
%global repo            ssm-server
%global provider_prefix	%{provider}.%{provider_tld}/%{project}/%{repo}

Name:		%{repo}
Version:	%{_version}
Release:	%{_release}
Summary:	Shattered Silicon Monitoring and Management Server

License:	AGPLv3
URL:		https://%{provider_prefix}
Source0:	%{name}-%{version}-%{release}.tar.gz

Requires:	nginx git bats


%description
Shattered Silicon Monitoring and Management (SSM) Server.
See the SSM docs for more information.


%prep
%setup -q -n %{name}
sed -i "s/ENV_SERVER_USER/${SERVER_USER:-ssm}/g" prometheus.yml prometheus1.yml
sed -i "s/ENV_SERVER_PASSWORD/${SERVER_PASSWORD:-ssm}/g" prometheus.yml prometheus1.yml
echo "${SERVER_USER:-ssm}:$(openssl passwd -apr1 ${SERVER_PASSWORD:-ssm})" > .htpasswd


%build


%install
install -d %{buildroot}%{_sysconfdir}/nginx/conf.d
mv .htpasswd  %{buildroot}%{_sysconfdir}/nginx/.htpasswd
mv nginx.conf %{buildroot}%{_sysconfdir}/nginx/conf.d/ssm.conf
mv nginx-ssl.conf %{buildroot}%{_sysconfdir}/nginx/conf.d/ssm-ssl.conf
install -d %{buildroot}%{_sysconfdir}/cron.daily
mv purge-qan-data %{buildroot}%{_sysconfdir}/cron.daily/purge-qan-data
install -d %{buildroot}%{_datadir}/ssm-dashboards
mv import-dashboards.py %{buildroot}%{_datadir}/ssm-dashboards/import-dashboards.py
install -d %{buildroot}%{_sysconfdir}/tmpfiles.d
mv tmpfiles.d-ssm.conf %{buildroot}%{_sysconfdir}/tmpfiles.d/ssm.conf

mv prometheus.yml %{buildroot}%{_sysconfdir}/prometheus.yml
mv prometheus1.yml %{buildroot}%{_sysconfdir}/prometheus1.yml

install -d %{buildroot}%{_sysconfdir}/consul
mv consul.json %{buildroot}%{_sysconfdir}/consul/consul.json

install -d %{buildroot}%{_sysconfdir}/my.cnf.d
mv my.cnf %{buildroot}%{_sysconfdir}/my.cnf.d/00-ssm.cnf
mv page.cnf %{buildroot}%{_sysconfdir}/my.cnf.d/page.cnf

install -d %{buildroot}%{_sysconfdir}/supervisord.d
mv supervisord.conf %{buildroot}%{_sysconfdir}/supervisord.d/ssm.ini

install -d %{buildroot}%{_datadir}/%{name}/landing-page/img
cp -pav ./entrypoint.sh %{buildroot}%{_datadir}/%{name}/entrypoint.sh
cp -pav ./landing-page/img/ssm-logo.png %{buildroot}%{_datadir}/%{name}/landing-page/img/ssm-logo.png
cp -pav ./zz-debug.cnf %{buildroot}%{_datadir}/%{name}/zz-debug.cnf
cp -pav ./ssm-migration.sql %{buildroot}%{_datadir}/%{name}/ssm-migration.sql


%files
%license LICENSE
%doc README.md CHANGELOG.md
%{_sysconfdir}/my.cnf.d
%{_sysconfdir}/supervisord.d
%{_sysconfdir}/consul
%{_sysconfdir}/prometheus.yml
%{_sysconfdir}/prometheus1.yml
%{_sysconfdir}/nginx/.htpasswd
%{_sysconfdir}/nginx/conf.d/ssm.conf
%{_sysconfdir}/nginx/conf.d/ssm-ssl.conf
%{_sysconfdir}/tmpfiles.d/ssm.conf
%{_sysconfdir}/cron.daily/purge-qan-data
%{_datadir}/ssm-dashboards/import-dashboards.py*
%{_datadir}/%{name}


%changelog
* Wed Sep 23 2020 Vadim Yalovets <vadim.yalovets@percona.com> - 1.17.5-22
- PMM-6268 upgrade angular to v10, CVE fix

* Fri Jun  5 2020 Mykyta Solomko <mykyta.solomko@percona.com> - 1.17.4-20
- PMM-5813 build password-page per installation type (OVF/AMI/Docker)

* Mon Jun 18 2018 Mykola Marzhan <mykola.marzhan@percona.com> - 1.12.0-11
- PMM-2629 add prometheus1 config

* Wed Mar 21 2018 Mykola Marzhan <mykola.marzhan@percona.com> - 1.9.0-10
- PMM-1823 add password page compilation

* Thu Nov 16 2017 Mykola Marzhan <mykola.marzhan@percona.com> - 1.5.0-6
- PMM-1708 use node_exporter from pmm-client

* Tue Aug 22 2017 Mykola Marzhan <mykola.marzhan@percona.com> - 1.3.0-5
- add supervisord.d config

* Tue Aug 22 2017 Mykola Marzhan <mykola.marzhan@percona.com> - 1.2.2-3
- add clickhouse.xml

* Tue Mar 14 2017 Mykola Marzhan <mykola.marzhan@percona.com> - 1.1.2-3
- add my.cnf

* Mon Feb 13 2017 Mykola Marzhan <mykola.marzhan@percona.com> - 1.1.0-2
- add version to landing page

* Thu Feb  9 2017 Mykola Marzhan <mykola.marzhan@percona.com> - 1.1.0-1
- add build_timestamp to Release value

* Wed Dec 28 2016 Mykola Marzhan <mykola.marzhan@percona.com> - 1.0.7-7
- add /etc/tmpfiles.d/pmm.conf file
- run systemd-tmpfiles tool during post install

* Wed Dec 28 2016 Mykola Marzhan <mykola.marzhan@percona.com> - 1.0.7-2
- add sysconfig

* Mon Dec 19 2016 Mykola Marzhan <mykola.marzhan@percona.com> - 1.0.7-1
- init version
