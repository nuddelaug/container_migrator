# Migrating Docker containers between Host

## purpose and scope of the tool

This small tool is ment for people who need to migrate their manually created containers from one PC to another.
For developers or people playing with Docker, it's most of the time not worth the effort deploying full Orchestration
tools like Kubernetes, OpenShift or others which provide such a functionality, _moving_ a container to another physical
host.

Self administrated Docker instances most often tend to be configured on an adhoc base and years later, we forgot how we
deployed a specific container which should be running in the _same_ state on another physical host including labels, port
mappings and mounts.

That's where this small script could come in handsome for you.

## clearly out of the scope for this tool

Be aware, this tool is not ment to _safe_ your life and or do Orchestration for you. It's ment to recreate a container on
another physical host with _more or less_ the same specifications as on the original host. With more or less, I mean ... 
the tool is not altering Dockers internal or similar. So don't expect that memory is transfered or the content of a persistent
storage.

## step by step howto

### requirements/pre requisits

as mentioned before, the intenden audiance is based on System Administrators or at least, the tool expects that you have super user
privileges to connect to Docker sockets and to gain access for syncing persistent storages. If you are without these privleges, the
tool will not be able to do anything for you.

* Docker socket connectivity, since we are talking about physical separated systems, preferable uri's are tcp://<hostname>:<port> 
* _root/privileged_ access to persistent container storage 
* python 3

### installation 

clone the source code and install the requirements. This can be done _system wide_ or with pythono virtual env.
```bash
git clone https://github.com/nuddelaug/container_migrator.git
pip install -r requirements.txt
```

### picking a container to be migrated

Pre evaluation considerations

* does the container use links to other containers, and are the available on the other host 
* does the destination target has enough space for hosting any/all persisten storage data
* does the destination target has access to _private_ images build on the old system

For all the questions above, none of them is _unsolve able_ but the tool cannot handle this for you. So for linked containers, ensure you know
the order of which to migrate first, second, ... 
If the container you want to migrate was build on the old host and or the image(s) used isn't public available, make sure to transfer the image(s)
first to the new Host using following docker commands

```bash
# dump the image required to space which is capable to hold the image size
docker image save -o /<enoughspace>/busybox.gz docker.io/busybox:latest

# transfer the tar'ed image to the new host for importing it with
docker image load -i /<enoughspace>/busybox.gz

# verify success of the image transfer
docker images | grep busybox
```

### calling the tool to start the migration

what, already but my storage ? Yes I expect that not everyone is familiar with how persistent storage is storing data or want to look it up so, the
tool will start the migration up until to the persisten volumes. 
This also means, for _scratch able_ containers with no persisten volumes, there's not much more to do.
But to make the howto complete, let's assume we have Persistent data ... 

I'll showcase the migration of HashiCorps Vault container, which maybe contains your credentials for various tests and re-entering all data would be 
a disaster.

```
docker_migration-tool.py -s tcp://127.0.0.1:2376 -d 192.168.0.1:2376 vault

checking Volume vault_private for existence
please syncronize following persisten volume:
vault_private: source:/var/lib/docker/volumes/vault_private/_data -> destination:/var/lib/docker/volumes/vault_private/_data


checking Volume 463758b5d5a4f11843d9f4c080d243472e5ecb6ef237f96df12abac4e19fb513 for existence
please syncronize following persisten volume:
463758b5d5a4f11843d9f4c080d243472e5ecb6ef237f96df12abac4e19fb513: source:/var/lib/docker/volumes/463758b5d5a4f11843d9f4c080d243472e5ecb6ef237f96df12abac4e19fb513/_data -> destination:/var/lib/docker/volumes/463758b5d5a4f11843d9f4c080d243472e5ecb6ef237f96df12abac4e19fb513/_data


!! please re-run the migration tool after you finished syncing !!
``` 

as you can see, the container has two volumes with persistent data, where in reality one doesn't contain anything but that's also out of the scope
of this tool to be able to decide.

#### syncronization of persistent storage

Assuming you have super user privileges as required above, you can after the first run of the migration-tool syncronize both persistent storages when
copying the source:/path and destination:/path into your rsync/winscp/...

``` 
# assuming you are on the source(old) host and transfer to the destination(new) host
rsync -avr /var/lib/docker/volumes/vault_private/_data/ root@192.168.0.1:/var/lib/docker/volumes/vault_private/_data/
```

yes, the script already created the persistent storage for you so the rsync/copy should be working out-of-the-box.
The time it takes to syncronize depends on how much data needs to be transfered. 

!!! DONT !!! run the script for the same container again until the synchronization is finished

### calling the tool to finish the migration

!!! DONT !!! continue until the synchronization is finished

coming back to the example and after the syncronization has finished we run the script identically again

```
docker_migration-tool.py -s tcp://127.0.0.1:2376 -d 192.168.0.1:2376 vault
checking Volume vault_private for existence
Volume vault_private exists, continue ...
checking Volume 463758b5d5a4f11843d9f4c080d243472e5ecb6ef237f96df12abac4e19fb513 for existence
Volume 463758b5d5a4f11843d9f4c080d243472e5ecb6ef237f96df12abac4e19fb513 exists, continue ...
migrated container vault succeeded
```

now we have a _copy_ of the original container on the new Host. But wait ... the container isn't running ? True !! As again the tool 
cannot predict if the container is _self contained_ or requires additional resources to be started/migrated it doesn't autostart your 
container. 
!!! DONT !!! re-run the migration-tool with ''--startup'', instead just call docker start <containername>.
If you want to do so after the migration is finished automatically, add ''--startup'' to the migration-tool for the second run. 

It transfered the settings for autostart of the original source, so the container will autostart next boot time.

```
docker inspect vault| grep -A3 RestartPolicy
            "RestartPolicy": {
                "Name": "always",
                "MaximumRetryCount": 0
            },
``` 

### special use cases 

!!! DONT !!! blame the script if your application doesn't work afterwards

#### ignoring linked containers

if the order of transfers conflicts with your priorities or isn't necessary but you need a copy on the remote side, you can skip link verification.
Be aware that any inside the container logic depending on such links (short connection strings to linked containers names) will fail as they are _stripped_
out to avoid Docker complaining about missing container for the configured links.

in the example below, we also assume persistent storage is already syncronized or there isn't any persistent storage
``` 
docker_migration-tool.py -s tcp://127.0.0.1:2376 -d 192.168.0.1:2376 --ignorelinks vault redis1 httpd ...
checking Volume vault_private for existence
Volume vault_private exists, continue ...
checking Volume 463758b5d5a4f11843d9f4c080d243472e5ecb6ef237f96df12abac4e19fb513 for existence
Volume 463758b5d5a4f11843d9f4c080d243472e5ecb6ef237f96df12abac4e19fb513 exists, continue ...
migrated container vault succeeded
checking Volume e5044301428cdd0d96ec2028ed18fd1e7bf4eb5be2dc573260a812b5246c7b03 for existence
Volume e5044301428cdd0d96ec2028ed18fd1e7bf4eb5be2dc573260a812b5246c7b03 exists, continue ...
migrated container redis1 succeeded
migrated container httpd succeeded
```

### renaming a container on the new host to avoid conflicts

the migration-tool can rename the container it will create for you on the new Host. Be aware that other depending containers will fail if the name isn't present.
Also notice that with ''--rename'' it's not possible to migrate more then one container with each run 

```
docker_migration-tool.py -s tcp://127.0.0.1:2376 -d 192.168.0.1:2376 --rename httpd brave_gates
renaming brave_gates to httpd
migrated container httpd succeeded
```
