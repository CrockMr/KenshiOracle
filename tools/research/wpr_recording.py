"""Own exactly one named WPR recording; never cancel another session."""

import _research_bootstrap  # Repository-relative imports for direct execution.
from pathlib import Path
import os
import subprocess


def command(*args):
    r=subprocess.run([os.environ.get('KENSHI_WPR') or 'wpr.exe',*args],capture_output=True,text=True,errors='replace',timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW)
    return dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)


class Recording:
    def __init__(self,instance,profile,root,runner=command):
        self.instance,self.profile,self.root=instance,Path(profile).resolve(),Path(root).resolve()
        self.runner=runner;self.commands={};self.started=False;self.cleanup_required=False

    def call(self,name,*args):
        try:self.commands[name]=self.runner(*args)
        except Exception as e:
            self.commands[name]=dict(error=str(e));raise
        return self.commands[name]

    @staticmethod
    def quiet(result):
        return result is not None and result.get('returncode')==0 and 'WPR is not recording' in result.get('stdout','')

    def verify_idle(self):
        result=self.call('status_before','-status')
        if not self.quiet(result):raise RuntimeError('Existing or unknown WPR recording; no recording will be stopped')

    def start(self):
        self.verify_idle()
        try:result=self.call('start','-start',str(self.profile)+'!KenshiCpu','-filemode','-recordtempto',str(self.root),'-instancename',self.instance)
        except Exception:
            self.recover_failed_start();raise
        if result['returncode']!=0:
            self.recover_failed_start()
            raise RuntimeError('WPR start failed: '+result['stdout']+result['stderr'])
        self.started=True;self.cleanup_required=True

    def recover_failed_start(self):
        # A timed-out controller can have enabled its collector already.
        try:status=self.call('status_after_failed_start','-status','collectors','-details','-instancename',self.instance)
        except Exception:status=None
        if self.quiet(status):return
        self.cleanup_required=True
        if status is not None and self.instance in status.get('stdout','') and 'WPR recording is in progress' in status.get('stdout',''):
            self.started=True

    def stop(self,trace):
        if not self.started:return
        stop=None;status=None
        try:stop=self.call('stop','-stop',str(Path(trace).resolve()),'-instancename',self.instance)
        except Exception:pass
        try:status=self.call('status_after_stop','-status','-instancename',self.instance)
        except Exception:pass
        if not self.quiet(status):
            # A successful start established ownership of this exact instance.
            try:self.call('cancel_owned','-cancel','-instancename',self.instance)
            except Exception:pass
            try:status=self.call('status_after_cancel','-status','-instancename',self.instance)
            except Exception:status=None
        self.cleanup_required=not self.quiet(status)
        self.started=self.cleanup_required
        if self.cleanup_required or stop is None or stop.get('returncode')!=0:
            raise RuntimeError('WPR stop failed; inspect named cleanup evidence')
