import sys
import logging
import binascii
from snimpy.snmp import Session

logger = logging.getLogger(__name__)

class SNMPCollector:
    def __init__(self):
        self.session = None
    
    def get_mac_table_v2c(self, host, community, oid):
        """Get MAC address table using SNMP v2c"""
        try:
            logger.info(f"Connecting to {host} with community {community}")
            session = Session(host=host, community=community, version=2)
            session.bulk = False
            
            result = session.walkmore(oid)
            mac_table = {}
            
            for _resultmib, value in result:
                rmib = list(_resultmib)
                # Extract IP from OID
                ip = "%s.%s.%s.%s" % (
                    rmib[-4:-3][0], rmib[-3:-2][0], 
                    rmib[-2:-1][0], rmib[-1:][0]
                )
                
                # Convert binary MAC to hex format
                macaddr = binascii.b2a_hex(value).decode('ascii')
                formatted_mac = "%s:%s:%s:%s:%s:%s" % (
                    macaddr[0:2], macaddr[2:4], macaddr[4:6],
                    macaddr[6:8], macaddr[8:10], macaddr[10:12]
                )
                
                mac_table[ip] = formatted_mac
                logger.debug(f"Found IP {ip} with MAC {formatted_mac}")
            
            del session
            logger.info(f"Retrieved {len(mac_table)} MAC entries from {host}")
            return mac_table
            
        except Exception as e:
            logger.error(f"Error collecting from {host}: {e}")
            return {}
    
    def get_mac_table_v3(self, host, oid, secname, authprotocol, authpassword, contextname):
        """Get MAC address table using SNMP v3"""
        try:
            logger.info(f"Connecting to {host} with SNMPv3 context {contextname}")
            session = Session(
                host=host, 
                version=3,
                secname=secname,
                authprotocol=authprotocol,
                authpassword=authpassword,
                contextname=contextname
            )
            session.bulk = False
            
            result = session.walkmore(oid)
            mac_table = {}
            
            for _resultmib, value in result:
                rmib = list(_resultmib)
                # Extract IP from OID
                ip = "%s.%s.%s.%s" % (
                    rmib[-4:-3][0], rmib[-3:-2][0], 
                    rmib[-2:-1][0], rmib[-1:][0]
                )
                
                # Convert binary MAC to hex format
                macaddr = binascii.b2a_hex(value).decode('ascii')
                formatted_mac = "%s:%s:%s:%s:%s:%s" % (
                    macaddr[0:2], macaddr[2:4], macaddr[4:6],
                    macaddr[6:8], macaddr[8:10], macaddr[10:12]
                )
                
                mac_table[ip] = formatted_mac
                logger.debug(f"Found IP {ip} with MAC {formatted_mac}")
            
            del session
            logger.info(f"Retrieved {len(mac_table)} MAC entries from {host} (context: {contextname})")
            return mac_table
            
        except Exception as e:
            logger.error(f"Error collecting from {host} context {contextname}: {e}")
            return {}
    
    def collect_from_router(self, router_config, router_name):
        """Collect MAC table from a router using its configuration"""
        if router_config['type'] == 'snmp_v2c':
            return self.get_mac_table_v2c(
                router_config['ip'],
                router_config['community'],
                router_config['query']
            )
        else:
            logger.warning(f"Unknown router type for {router_name}: {router_config['type']}")
            return {}
    
    def collect_from_firewall(self, firewall_config, firewall_name):
        """Collect MAC tables from firewall using SNMPv3 with multiple contexts"""
        all_macs = {}
        
        for context in firewall_config['contexts']:
            mac_table = self.get_mac_table_v3(
                firewall_config['ip'],
                firewall_config['query'],
                firewall_config['secname'],
                firewall_config['authprotocol'],
                firewall_config['authpassword'],
                context
            )
            
            # Merge results
            all_macs.update(mac_table)
        
        logger.info(f"Total {len(all_macs)} MAC entries from firewall {firewall_name}")
        return all_macs
    
    def read_f5_file(self, filepath):
        """Read MAC addresses from F5 load balancer file"""
        mac_table = {}
        try:
            with open(filepath, 'r') as f:
                for line in f.readlines():
                    parts = line.strip().split(" ")
                    if len(parts) >= 2:
                        ip = parts[0]
                        mac = parts[1].strip()
                        mac_table[ip] = mac
                        logger.debug(f"F5 file: IP {ip} MAC {mac}")
            
            logger.info(f"Read {len(mac_table)} entries from F5 file {filepath}")
            return mac_table
            
        except Exception as e:
            logger.error(f"Error reading F5 file {filepath}: {e}")
            return {} 