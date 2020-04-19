#!/usr/bin/env python3

import sys
try:
    from termcolor import colored
except ImportError:
    print ('not able to color the output, pay attention')
    def colored(what, color):
        return what

try:
    import docker
    import docker.errors
except ImportError:
    print ('you need to install python-docker, like pip install docker', 'red')
    sys.exit(1)

import optparse
import json

def map_volumes(volumes):
    voldict, binddict = {}, []
    for vol in volumes:
        vtype, state = vol['Type'], vol['RW']
        if state == True:       state = 'rw'
        else:                   state = 'ro'
        if vtype == 'bind':
            vol['Target'] = vol['Destination']
            binddict.append(vol)
        else:
            name, dest = vol['Name'], vol['Destination']
            voldict[name] = {'bind': dest, 'mode': state}
    return voldict, binddict

def map_container(config):
    cfgdict, links = {}, {}
    cfgdict['image'] = config['Config']['Image']
    cfgdict['command'] = config['Config']['Cmd']
    cfgdict['environment'] = config['Config']['Env']
    cfgdict['entrypoint'] = config['Config']['Entrypoint']
    cfgdict['labels'] = config['Config']['Labels']
    cfgdict['privileged'] = config['HostConfig']['Privileged']
    cfgdict['name'] = config['Name']
    cfgdict['volumes'], cfgdict['mounts'] = map_volumes(config['Mounts'])
    cfgdict['restart_policy'] = config['HostConfig']['RestartPolicy']
    cfgdict['publish_all_ports'] = config['HostConfig']['PublishAllPorts']
    cfgdict['read_only'] = config['HostConfig']['ReadonlyRootfs']
    cfgdict['ports'] = config['NetworkSettings']['Ports']
    cfgdict['network_mode'] = config['HostConfig']['NetworkMode']
    cfgdict['hostname'] = config['Config']['Hostname']
    cfgdict['domainname'] = config['Config']['Domainname']
    cfgdict['detach'] = True
    if config['HostConfig']['Links'] != None:
        for link in config['HostConfig']['Links']:
            k, v = link.split(':', 1)
            links[k] = v
    cfgdict['links'] = links                       
    return cfgdict

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('-s', '--source', action='store', default=False)
    parser.add_option('-d', '--destination', action='store', default=False)
    parser.add_option('--ignorelinks', action='store_true', default=False)
    parser.add_option('--startup', action='store_true', default=False)
    parser.add_option('--rename', action='store', default=False)
    options, remainings = parser.parse_args()
    
    if not all([ options.source, options.destination, remainings != []]):
        print (colored('you need to specify at least source, destination and one container', 'red'))
        print (parser.print_help())
        sys.exit(1)
    
    ctrls = {'source': {'ctrl': None, 'uri': options.source},
             'dest':   {'ctrl': None, 'uri': options.destination}}
    for ctrl in ctrls.values():
        try:
            ctrl['ctrl'] = docker.DockerClient(base_url=ctrl['uri'])
            if not ctrl['ctrl'].ping():    raise Exception('Docker doesnt respond to ping')
        except Exception as e:
            print (colored('accessing Docker socket at uri %s failed with: %s' % (ctrl['uri'], str(e)), 'red'))
            sys.exit(1)
    sctrl, dctrl = ctrls['source']['ctrl'], ctrls['dest']['ctrl']
    
    for name in remainings:
        try:    container   = sctrl.containers.get(name)
        except docker.errors.NotFound:
            print (colored('skipping container %s, not found at %s' % (name, options.source), 'blue'))
            continue
        cfg         = map_container(container.attrs)
        missingvolumes = False
        for volume in cfg['volumes']:
            print (colored('checking Volume %s for existence' % volume, 'blue'))
            try:
                dctrl.volumes.get(volume)
                print (colored('Volume %s exists, continue ...' % volume, 'green'))
            except docker.errors.NotFound:
                dv = dctrl.volumes.create(volume)
                sv = sctrl.volumes.get(volume)
                print (colored('please syncronize following persisten volume:', 'red'))
                print (colored('%s: source:%s -> destination:%s\n\n' % (volume, sv.attrs['Mountpoint'],
                                                                        dv.attrs['Mountpoint']), 'red'))
                missingvolumes = True
        if missingvolumes:
            print (colored('!! please re-run the migration tool after you finished syncing !!', 'green'))
            sys.exit(0)
        if all([cfg.get('links') != {},
                options.ignorelinks == False]):
            for link in cfg.get('links'):
                try:    dctrl.containers.get(link)
                except docker.errors.NotFound:
                    print (colored('cannot migrate container %s due to missing link %s' % (name, link), 'red'))
                    sys.exit(2)
        try:    image   = dctrl.images.get(cfg['image'])
        except docker.errors.NotFound:
            try:
                dctrl.images.pull(cfg['image'])
                print (colored('fetchting image %s' % cfg['image'], 'green'))
            except docker.errors.ImageNotFound:
                print (colored('cannot run container %s due to missing image %s' % (name, cfg['image']), 'red'))
                print (colored('please make sure the image is public available or push it to the destination host'), 'red')
                sys.exit(4)
        if all([options.rename != False, len(remainings) == 1]):
            print (colored('renaming %s to %s'% (name, options.rename), 'blue'))
            name = options.rename
            cfg['name'] = name
        elif all([options.rename != False]):
            print (colored('ignoring rename of destination container as you specified more then one', 'blue'))
        try:
            dverify    = dctrl.containers.get(name)
            print (colored('Conflicting container found on destination:', 'red'))
            dcfg       = map_container(dverify.attrs)
            print (colored('Name: %s Image: %s' % (dcfg['name'], dcfg['image']), 'red'))
            print (colored(json.dumps(dcfg, indent=2), 'yellow'))
            sys.exit(3)
        except docker.errors.NotFound:
            try:
                dcontainer = dctrl.containers.create(**cfg)
                print (colored('migrated container %s succeeded' % name, 'green'))
                if options.startup:
                    print (colored('starting up container %s' % name, 'green'))
                    dcontainer.start()
            except Exception as e:
                print (colored('unable to create container %s:' % name, 'red'))
                print (colored(str(e), 'red'))
                               
