#!/usr/bin/env python

import argparse
import pysam
import os
import logging
import subprocess

"""This script runs SomaticSniper
Required Option:
        -f FILE   REQUIRED reference sequence in the FASTA format

Options:
        -v        Display version information

        -q INT    filtering reads with mapping quality less than INT [0]
        -Q INT    filtering somatic snv output with somatic quality less than  INT [15]
        -L FLAG   do not report LOH variants as determined by genotypes
        -G FLAG   do not report Gain of Reference variants as determined by genotypes
        -p FLAG   disable priors in the somatic calculation. Increases sensitivity for solid tumors
        -J FLAG   Use prior probabilities accounting for the somatic mutation rate
        -s FLOAT  prior probability of a somatic mutation (implies -J) [0.010000]
        -T FLOAT  theta in maq consensus calling model (for -c/-g) [0.850000]
        -N INT    number of haplotypes in the sample (for -c/-g) [2]
        -r FLOAT  prior of a difference between two haplotypes (for -c/-g) [0.001000]
        -n STRING normal sample id (for VCF header) [NORMAL]
        -t STRING tumor sample id (for VCF header) [TUMOR]
        -F STRING select output format [classic]
           Available formats:
             classic
             vcf
             bed
"""

def sniper_argparser():
    parser = argparse.ArgumentParser(description='Run SomaticSniper')
    parser.add_argument('-f', metavar='REFERENCE', required=True, help='reference sequence in the FASTA format')
    parser.add_argument('-q', required=False, metavar='MAPQ', type=int, help='filtering reads with mapping quality less than [%(default)s]', default=0)
    parser.add_argument('-Q', required=False, metavar='SOMATICQ', type=int, help='filtering somatic snv output with somatic quality less than [%(default)s]', default=15)
    parser.add_argument('-L', required=False, action='store_true', help='do not report LOH variants as determined by genotypes')
    parser.add_argument('-G', required=False, action='store_true', help='do not report Gain of Reference variants as determined by genotypes')
    parser.add_argument('-p', required=False, action='store_true', help='disable priors in the somatic calculation. Increases sensitivity for solid tumors')
    parser.add_argument('-J', required=False, action='store_true', help='Use prior probabilities accounting for the somatic mutation rate')
    parser.add_argument('-s', required=False, metavar='SOMATIC_PRIOR',type=float, help='prior probability of a somatic mutation (implies -J) [%(default)s]', default=0.01)
    #parser.add_argument('-T', required=False, metavar='THETA', type=float, help='theta in maq consensus calling model [%(default)s]', default=0.85)
    #parser.add_argument('-N', required=False, metavar='NUM_HAPLOTYPES', type=int, help='number of haplotypes in the sample [%(default)s]', default=2)
    parser.add_argument('-r', required=False, metavar='GERMLINE_PRIOR', type=float, help='prior of a difference between two haplotypes [%(default)s]', default=0.001)
    parser.add_argument('-n', required=True, metavar='NORMAL_NAME', help='normal sample id (for VCF header) [%(default)s]', default='NORMAL')
    parser.add_argument('-t', required=True, metavar='TUMOR_NAME', help='tumor sample id (for VCF header) [%(default)s]', default='TUMOR')
    parser.add_argument('-F', required=True, metavar='FORMAT', choices=('classic', 'vcf', 'bed'), help='select output format [%(default)s]', default='vcf')
    parser.add_argument('tumor_bam', help='tumor BAM file')
    parser.add_argument('normal_bam', help='normal BAM file')
    parser.add_argument('output', help='Output file')
 
    group = parser.add_argument_group('wrapper specific options')
    group.add_argument('--workdir', default='/tmp/', help='Working directory of the wrapper')
    group.add_argument('--tumor-uuid', dest='tumor_uuid', help='Tumor CGHub analysis id')
    group.add_argument('--normal-uuid', dest='normal_uuid', help='Normal CGHub analysis id')
    group.add_argument('--sniper-exe', dest='sniper_exe', default='bam-somaticsniper', help='Normal CGHub analysis id')
    return parser

def create_sniper_opts(namespace_dict):
    args = []
    flag_opts = set(('L','G','p','J'))
    wrapper_arguments = set(('f', 'tumor_bam', 'normal_bam', 'output', 'workdir', 'tumor_uuid', 'normal_uuid', 'sniper_exe'))
    for option, value in namespace_dict.items():
        if option in wrapper_arguments:
            continue
        if (option in flag_opts):
            if value:
                args.append("-" + option)
        else:
            args.append("-" + option + " " + str(value)) 
    return " ".join(args)

def create_sniper_cmdline(namespace_dict, reference, tumor_bam, normal_bam, temp_output_file):
    return " ".join([
        namespace_dict['sniper_exe'],
        create_sniper_opts(namespace_dict),
        "-f " + reference,
        tumor_bam, 
        normal_bam,
        temp_output_file])

def create_workspace(workdir, reference, tumor_bam, normal_bam):
    #need to symlink in stuff
    symlink_workspace_file(workdir, reference + ".fai" , "ref_genome.fasta.fai"),
    return ( 
            symlink_workspace_file(workdir, tumor_bam, "tumor.bam"),
            symlink_workspace_file(workdir, normal_bam, "normal.bam"),
            symlink_workspace_file(workdir, reference, "ref_genome.fasta"),
            )
    
def symlink_workspace_file(workdir, original_file, new_file):
    symlink_name = os.path.join(workdir, new_file)
    os.symlink(os.path.abspath(original_file), symlink_name)
    return symlink_name

def sample_from_bam(bam_file):
    file = pysam.Samfile(bam_file) #this may need to be AlignmentFile depending on pysam version
    readgroups = file.header['RG']
    samples = set()
    for readgroup in readgroups:
        samples.add(readgroup['SM'])
    assert(len(samples) == 1)
    return samples.pop()

def reheader_vcf(original_vcf_file, new_vcf_file):
    #need to add fields for the samples to the VCF header? as well as other info we add in Genome::Model::Tools::Vcf::Convert::Base.pm
    pass

def execute(options, ref, tumor, normal, temp_output_file):
    cmd = create_sniper_cmdline(options, ref, tumor, normal, temp_output_file)

    logging.info("RUNNING: %s" % (cmd))
    print "running", cmd
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    stdout, stderr = p.communicate()
    if len(stderr):
        print stderr
    return p.returncode

if __name__ == "__main__":
    parser = sniper_argparser()
    args = parser.parse_args()
    #opt_string = create_sniper_opts(vars(args))

    #tumor_sample_name = sample_from_bam(args.tumor_bam)
    #normal_sample_name = sample_from_bam(args.normal_bam)

    (workspace_tumor, workspace_normal, workspace_ref) = create_workspace(args.workdir, args.f, args.tumor_bam, args.normal_bam)
    temp_output_file = os.path.join(args.workdir, "raw_output.vcf")
    
    execute(vars(args), workspace_ref, workspace_tumor, workspace_normal, temp_output_file)
    reheader_vcf(temp_output_file, args.output)

