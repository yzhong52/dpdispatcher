import os,getpass,time
from dpgen.dispatcher.Batch import Batch
from dpgen.dispatcher.JobStatus import JobStatus

def _default_item(resources, key, value) :
    if key not in resources :
        resources[key] = value

def _set_default_resource(res_) :
    if res_ == None :
        res = {}
    else:
        res = res_
    _default_item(res, 'numb_node', 1)
    _default_item(res, 'task_per_node', 1)
    _default_item(res, 'cpus_per_task', 1)
    _default_item(res, 'numb_gpu', 0)
    _default_item(res, 'time_limit', '1:0:0')
    _default_item(res, 'mem_limit', -1)
    _default_item(res, 'partition', '')
    _default_item(res, 'account', '')
    _default_item(res, 'qos', '')
    _default_item(res, 'constraint_list', [])
    _default_item(res, 'license_list', [])
    _default_item(res, 'exclude_list', [])
    _default_item(res, 'module_unload_list', [])
    _default_item(res, 'module_list', [])
    _default_item(res, 'source_list', [])
    _default_item(res, 'envs', None)
    _default_item(res, 'with_mpi', False)
    _default_item(res, 'cuda_multi_tasks', False)
    _default_item(res, 'allow_failure', False)
    _default_item(res, 'cvasp', False)
    return res

    
class Slurm(Batch) :

    def sub_cmd(self) :
        return 'sbatch'

    def sub_script(self,
                   job_dirs,
                   cmd,
                   args = None,
                   res  = None,
                   outlog = 'log',
                   errlog = 'err') :
        """
        make submit script

        job_dirs(list):         directories of jobs. size: n_job
        cmd(list):              commands to be executed. size: n_cmd
        args(list of list):     args of commands. size of n_cmd x n_job
                                can be None
        res(dict):              resources available
        outlog(str):            file name for output
        errlog(str):            file name for error
        """

        res = _set_default_resource(res)
        ret = self._script_head(res)

        if not isinstance(cmd, list):
            cmd = [cmd]
        if args == None :
            args = []
            for ii in cmd:
                _args = []
                for jj in job_dirs:
                    _args.append('')
                args.append(_args)
        try:
            cvasp=res['cvasp']
            fp_max_errors = 3
            try:
                fp_max_errors = res['fp_max_errors']
            except:
                pass
        except:
            cvasp=False

        # loop over commands 
        for ii in range(len(cmd)):            
            # for one command
            ret += self._script_cmd(res,
                                    job_dirs,
                                    cmd,
                                    args,
                                    ii,
                                    outlog=outlog,
                                    errlog=errlog,
                                    cvasp=cvasp,
                                    fp_max_errors=fp_max_errors)
        ret += '\ntouch tag_finished\n'
        return ret

        
    def check_sub_limit(self, task_max, **kwarg) :
        if task_max <= 0:
            return True
        username = getpass.getuser()
        stdin, stdout, stderr = self.context.block_checkcall('squeue -u %s -h' % username)
        nj = len(stdout.readlines())
        return nj < task_max


    def check_status(self) :
        job_id = self.get_job_id()
        if job_id == '' :
            return JobStatus.terminated
        while True:
            stat = self._check_status_inner(job_id)
            if stat != JobStatus.completing:
                return stat
            else:
                time.sleep(5)

    def _check_status_inner(self, job_id):
        ret, stdin, stdout, stderr\
            = self.context.block_call ("squeue --job " + job_id)
        if (ret != 0) :
            err_str = stderr.read().decode('utf-8')
            if str("Invalid job id specified") in err_str :
                if self.check_finish_tag() :
                    return JobStatus.finished
                else :
                    return JobStatus.terminated
            else :
                raise RuntimeError\
                    ("status command squeue fails to execute\nerror message:%s\nreturn code %d\n" % (err_str, ret))
        status_line = stdout.read().decode('utf-8').split ('\n')[-2]
        status_word = status_line.split ()[-4]
        if status_word in ["PD","CF","S"] :
            return JobStatus.waiting
        elif status_word in ["R"] :
            return JobStatus.running
        elif status_word in ["CG"] :
            return JobStatus.completing
        elif status_word in ["C","E","K","BF","CA","CD","F","NF","PR","SE","ST","TO"] :
            if self.check_finish_tag() :
                return JobStatus.finished
            else :
                return JobStatus.terminated
        else :
            return JobStatus.unknown        
            

    def _script_head(self,
                     res):
        ret = ''
        ret += "#!/bin/bash -l\n"
        ret += "#SBATCH -N %d\n" % res['numb_node']
        ret += "#SBATCH --ntasks-per-node %d\n" % res['task_per_node']
        if res['cpus_per_task'] > 0 :            
            ret += "#SBATCH --cpus-per-task %d\n" % res['cpus_per_task']
        ret += "#SBATCH -t %s\n" % res['time_limit']
        if res['mem_limit'] > 0 :
            ret += "#SBATCH --mem %dG \n" % res['mem_limit']
        if len(res['account']) > 0 :
            ret += "#SBATCH --account %s \n" % res['account']
        if len(res['partition']) > 0 :
            ret += "#SBATCH --partition %s \n" % res['partition']
        if len(res['qos']) > 0 :
            ret += "#SBATCH --qos %s \n" % res['qos']
        if res['numb_gpu'] > 0 :
            ret += "#SBATCH --gres=gpu:%d\n" % res['numb_gpu']
        for ii in res['constraint_list'] :
            ret += '#SBATCH -C %s \n' % ii
        for ii in res['license_list'] :
            ret += '#SBATCH -L %s \n' % ii
        if len(res['exclude_list']) >0:
            temp_exclude = ""
            for ii in res['exclude_list'] :
                temp_exclude += ii
                temp_exclude += ","
            temp_exclude = temp_exclude[:-1]
            ret += '#SBATCH --exclude %s \n' % temp_exclude
        ret += "\n"
        for ii in res['module_unload_list'] :
            ret += "module unload %s\n" % ii
        for ii in res['module_list'] :
            ret += "module load %s\n" % ii
        ret += "\n"
        for ii in res['source_list'] :
            ret += "source %s\n" %ii
        ret += "\n"
        envs = res['envs']
        if envs != None :
            for key in envs.keys() :
                ret += 'export %s=%s\n' % (key, envs[key])
            ret += '\n'        
        return ret


    def _script_cmd(self,
                    res,
                    job_dirs,
                    cmd,
                    args,
                    idx,
                    outlog = 'log',
                    errlog = 'err',
                    cvasp = False,
                    fp_max_errors = 3) :
        ret = ""
        for ii,jj in zip(job_dirs, args[idx]) :
            ret += 'cd %s\n' % ii
            ret += 'test $? -ne 0 && exit\n\n'
            _cmd = cmd[idx].split('1>')[0].strip()
            if cvasp :
                if res['with_mpi']:
                    _cmd = 'python ../cvasp.py "srun %s" %s' % (_cmd, fp_max_errors)
                else :
                    _cmd = 'python ../cvasp.py "%s" %s' % (_cmd, fp_max_errors)
            else :
                if res['with_mpi']:
                    _cmd = 'srun %s ' % (_cmd)
                else :
                    _cmd = '%s ' % (_cmd)
            _cmd += ' %s 1> %s 2> %s ' % (jj, outlog, errlog)
            ret += 'if [ ! -f tag_%d_finished ] ;then\n' % idx
            ret += '  %s\n' % (_cmd)
            if res['allow_failure'] is False:
                ret += '  if test $? -ne 0; then exit; else touch tag_%d_finished; fi \n' % idx
            ret += 'fi\n\n'
            ret += 'cd %s\n' % self.context.remote_root
            ret += 'test $? -ne 0 && exit\n'
        return ret
