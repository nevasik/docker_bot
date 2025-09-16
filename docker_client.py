import asyncio
import subprocess
import json
import psutil
from typing import List, Dict, Any

class DockerClient:
    """Клиент для работы с Docker через SSH"""
    
    def __init__(self):
        self.host = os.getenv('SERVER_HOST')
        self.user = os.getenv('SERVER_USER')
        self.password = os.getenv('SERVER_PASSWORD')
        
    async def _run_ssh_command(self, command: str) -> str:
        """Выполнить команду через SSH"""
        ssh_command = [
            'sshpass', '-p', self.password,
            'ssh', '-o', 'StrictHostKeyChecking=no',
            f'{self.user}@{self.host}',
            command
        ]
        
        process = await asyncio.create_subprocess_exec(
            *ssh_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"SSH команда завершилась с ошибкой: {stderr.decode()}")
            
        return stdout.decode()
    
    async def get_containers(self) -> List[Dict[str, Any]]:
        """Получить список контейнеров"""
        command = "docker ps -a --format '{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}'"
        result = await self._run_ssh_command(command)
        
        containers = []
        for line in result.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 4:
                    containers.append({
                        'id': parts[0],
                        'name': parts[1],
                        'status': parts[2],
                        'image': parts[3]
                    })
        
        return containers
    
    async def get_container_info(self, container_id: str) -> Dict[str, Any]:
        """Получить подробную информацию о контейнере"""
        command = f"docker inspect {container_id}"
        result = await self._run_ssh_command(command)
        
        try:
            data = json.loads(result)[0]
            return {
                'id': data['Id'][:12],
                'name': data['Name'][1:],  # убираем первый символ '/'
                'status': data['State']['Status'],
                'image': data['Config']['Image'],
                'created': data['Created'][:19].replace('T', ' ')
            }
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            raise Exception(f"Ошибка при парсинге информации о контейнере: {e}")
    
    async def start_container(self, container_id: str) -> bool:
        """Запустить контейнер"""
        command = f"docker start {container_id}"
        await self._run_ssh_command(command)
        return True
    
    async def stop_container(self, container_id: str) -> bool:
        """Остановить контейнер"""
        command = f"docker stop {container_id}"
        await self._run_ssh_command(command)
        return True
    
    async def restart_container(self, container_id: str) -> bool:
        """Перезапустить контейнер"""
        command = f"docker restart {container_id}"
        await self._run_ssh_command(command)
        return True
    
    async def get_container_logs(self, container_id: str, lines: int = 50) -> str:
        """Получить логи контейнера"""
        command = f"docker logs --tail {lines} {container_id}"
        return await self._run_ssh_command(command)
    
    async def get_images(self) -> List[Dict[str, Any]]:
        """Получить список образов"""
        command = "docker images --format '{{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}'"
        result = await self._run_ssh_command(command)
        
        images = []
        for line in result.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 4:
                    images.append({
                        'name': f"{parts[0]}:{parts[1]}",
                        'size': parts[2],
                        'created': parts[3][:19].replace('T', ' ')
                    })
        
        return images
    
    async def get_stats(self) -> Dict[str, Any]:
        """Получить статистику сервера"""
        command = "docker stats --no-stream --format '{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'"
        result = await self._run_ssh_command(command)
        
        cpu_percent = 0
        memory_percent = 0
        
        if result.strip():
            lines = result.strip().split('\n')
            if lines:
                parts = lines[0].split('\t')
                if len(parts) >= 3:
                    cpu_percent = float(parts[0].replace('%', ''))
                    memory_percent = float(parts[2].replace('%', ''))
        
        containers = await self.get_containers()
        running_containers = len([c for c in containers if c['status'].startswith('Up')])
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'disk_percent': 0,  # можно добавить получение через df
            'containers': f"{running_containers}/{len(containers)}"
        }
