#!/usr/bin/env python

##print __name__

import os
import optparse
import re

usage_line = """
genotypes_from_VCF.py

Version 1.0 (12 May, 2015)
License: GNU GPLv2
To report bugs or errors, please contact Daren Card (dcard@uta.edu).
This script is provided as-is, with no support and no guarantee of proper or desirable functioning.

Script that takes VCF file and parses it to produce input files for downstream analysis. Will produce:
	1. An output VCF based on the user defined MAF ranges
	2. An input file for Entropy (Gompert & Buerkle), as well as appropriate starting points for the MCMC
	3. A FASTA nucleotide alignment (with IUPAC ambiguities) for phylogenetic analysis (i.e., RAxML)
	4. A FASTA trinary genotype alignment for phylogenetic analysis (i.e., SNAPP)

The script uses a sample sheet to correctly parse the desired samples, which is a tab-delimited text file \
with four columns: (1) BAM input file name, (2) Sample name, (3) Population ID, and (4) Location. \
User must also designate the MAF range desired for the run (this represents minimal output). \
User can specify any combination of the three outputs by using the appropriate flag. In the case of \
Entropy, starting and ended K values should be provided for creating the MCMC chain starting points. \
For the nucleotide and trinary alignments, a genotype quality threshold is needed so that unreliable \
sites can be coded as missing data (?). There is also the option to thin the number of SNPs by \
only taking 1 SNP per 10 kb, so as not to violate the assumptions of many models that dictate SNPs \
should be independent (i.e., not linked). The user specifies a naming prefix that will be used for \
naming the output files created. The suffixes for the different file types are as follows:
	1. Output VCF filtered by MAF and possibly thinned: .maf<#>.recode.vcf
	2. Entropy input: .entropy
	3. Entropy MCMC initialization (for each K): .entropy.startK<#>
	4. IN DEVELOPMENT: Various R plots from K-means clustering: .kmean.K<#>.plot
	5. IN DEVELOPMENT: Various R plots from discriminant analysis: .dapc.plot
	6. Nucleotide FASTA: .nucl.fasta
	7. Trinary FASTA: .tri.fasta
	8. Log files: .maf<#>.log (needs to be saved if specifying filtered VCF)
	
Dependencies include the latest versions of R, with the package MASS installed, and VCFtools, all \
included in the user's $PATH. The user should provide an input VCF that has already been filtered \
based upon factors like base quality, mapping quality, and missing data. This VCF must include the \
GP, GL, and GQ format/genotype flags.

python genotypes_from_VCF.py --samplsheet <samplesheet.txt> --vcf <in.vcf> --prefix <out_prefix> \
--maf <1-3> [--entropy --startK <#> --endK <#> --nucl --trinary --gq <PHRED_genotype_quality> --ind]
"""


#################################################
###           Parse command options           ###
#################################################

usage = usage_line
                        
parser = optparse.OptionParser(usage = usage)
parser.add_option("--samplesheet", action= "store", type = "string", dest = "sheet", help = "sample sheet containing samples being processed")
parser.add_option("--vcf", action = "store", type = "string", dest = "vcf", help = "VCF input file")
parser.add_option("--prefix", action = "store", dest = "prefix", help = "prefix for output files [out]", default = "out")
#parser.add_option("--entropy", action = "store_true", dest = "entropy", help = "create entropy input file and proper starting points [TRUE]", default = "True")
#parser.add_option("--startK", action = "store", dest = "sK", help = "starting (lower) K [1]", default = "1")
#parser.add_option("--endK", action = "store", dest = "eK", help = "ending (higher) K [5]", default = "2")
parser.add_option("--nucl", action = "store_true", dest = "nucl", help = "create nucleotide FASTA alignment with IUPAC ambiguities for heterozygous sites [TRUE]", default = False)
parser.add_option("--trinary", action = "store_true", dest = "tri", help = "create trinary FASTA alignment with 0, 1, 2 genotype codes [TRUE]", default = False)
parser.add_option("--genotype", action = "store", dest = "genotype", help = "type of genotype likelihood output: 0 = PHRED, 1 = -Log10, 2 = Standardized, 3 = Genotype Uncertainty [0]", default = "0")
parser.add_option("--gq", action = "store", dest = "gq", help = "threshold genotype quality for reporting individual genotype (otherwise coded as missing - ?) [20]", default = "20")
parser.add_option("--ind", action = "store_true", dest = "ind", help = "thin dataset to only include 1 SNP per 10 kb, so as to reduce chance of linked SNPs [TRUE]", default = "True")
parser.add_option("--thin", action = "store", dest = "thin", help = "window size to use for thinning in bp (keeps first SNP it finds and ignores others) [10000]", default = "10000")
parser.add_option("--maf", action = "store", dest = "maf", help = "the minor allele frequency range desired: 0 (all MAF), 1 (MAF >= 0.050), 2 (0.010 <= MAF < 0.050), 3 (MAF < 0.050) [1]", default = "1") 
parser.add_option("--locinfo", action = "store_true", dest = "locinfo", help = "include locus positional information (format = chromosome_position) in genotype matrix [FALSE]", default = False)
parser.add_option("--refalt", action = "store_true", dest = "refalt", help = "include reference and alternative alleles in genotype matrix [FALSE]", default = False)
parser.add_option("--headers", action = "store", dest = "headers", help = "specify which type of header to include in the genotype matrix (comma separated): 0 = none, 1 = matrix dimensions, 2 = sample IDs, 3 = population IDs, 4 = position and reference/alternative headers [1,2,3,4]", default = "1,2,3,4")
parser.add_option("--delimit", action = "store", dest = "delimit", help = "specify which delimiter to use for the genotype matrix: 1 = space, 2 = tab [1]", default = "1")
parser.add_option("--filvcf", action = "store", type = "string", dest = "filvcf", help ="specify a filtered VCF for genotyping (e.g., re-running a script) - bipasses creating new VCF [N/A]", default = "")

options, args = parser.parse_args()


#################################################
###       Filter VCF using user input         ###
#################################################

## Determine user input for MAF and thinning and use it to construct VCFtools, then run command
def vcf_filter():
	## MAF routine
	if options.maf == "0":
		vcf_maf = "--maf 0.0000001"
		print "\n\n***VCF will not be filtered by MAF***\n\n"
	elif options.maf == "1":
		vcf_maf = "--maf 0.0500"
		print "\n\n***Filtering VCF to MAF >= 0.05***\n\n"
	elif options.maf == "2":
		vcf_maf = "--maf 0.0100000 --max-maf 0.0499999"
		print "\n\n***Filtering VCF to 0.01 <= MAF < 0.05***\n\n"
	elif options.maf == "3":
		vcf_maf = "--maf 0.0000001 --max-maf 0.0499999"
		print "\n\n***Filtering VCF to MAF < 0.05***\n\n"
	else:
		print "\n\n***Error: a minor allele range needs to be specified!***\n\n"
	
	## construct MAF filtering command and run it
	command = "vcftools --vcf "+str(options.vcf)+" "+str(vcf_maf)+" --recode --recode-INFO-all --out "+str(options.prefix)+".maf"+str(options.maf)
	print "\n\n###Using the following command with VCFtools to produce MAF filtered VCF###\n\n"
	print command
	os.system(command)

	## Thinning routine (if applicable)
	if options.ind is True:
		vcf_thin = options.thin
		print "\n\n***Thinning to one SNP per 10 kb using the following command***\n\n"
		command = "vcftools --vcf "+str(options.prefix)+".maf"+str(options.maf)+".recode.vcf --thin "+str(vcf_thin)+" --recode --recode-INFO-all --out "+str(options.prefix)+".thin"
		print command
		os.system(command)
		os.system("mv "+options.prefix+".thin.recode.vcf "+options.prefix+".maf"+options.maf+".recode.vcf")
	else:
		vcf_thin = ""
		print "\n\n***No thinning will be performed***\n\n"
	print "\n\n###The filtered VCF is named "+options.prefix+".maf"+options.maf+".recode.vcf###\n\n"


#################################################
###      Creating Genotype matrix output      ###
#################################################

## Create input file for Entropy program using sample sheet and VCF
def geno_matrix(PL, filtered_vcf, delimiter):
	## Initialize output file
	genomatrix_out = open(options.prefix+".genomatrix", "w")
	
	## Get matrix dimensions (samples x loci) from VCFtools log
	if "1" in options.headers:
		[samples, loci] = get_vcf_dims()
		genomatrix_out.write(samples+str(delimiter)+loci+str(delimiter)+"1\n")
	
	sample_total = file_len(options.sheet)
	
	## Output line of sample names from second column of sample sheet
	if "2" in options.headers:
		if options.locinfo is True:
			if "4" in options.headers:
				genomatrix_out.write("Marker"+delimiter)
		if options.refalt is True:
			if "4" in options.headers:
				genomatrix_out.write("Ref."+delimiter+"Alt."+delimiter)
		for sline in open(options.sheet, "r"):
			if not sline.strip().startswith("#"):
				bar = sline.rstrip().split("\t")
				if "3" in options.genotype:
					l1out = bar[1]+str(delimiter)
				elif "0" or "1" or "2" in options.genotype:
					l1out = bar[1]+str(delimiter)+bar[1]+str(delimiter)+bar[1]+str(delimiter)
				genomatrix_out.write(l1out)
		genomatrix_out.write("\n")
	
	## Output line of sample populations from third column of sample sheet
	if "3" in options.headers:
		if options.locinfo is True:
			if "4" in options.headers:
				genomatrix_out.write("Marker"+delimiter)
		if options.refalt is True:
			if "4" in options.headers:
				genomatrix_out.write("Ref."+delimiter+"Alt."+delimiter)
		for sline in open(options.sheet, "r"):
			if not sline.strip().startswith("#"):
				bar = sline.rstrip().split("\t")
				if "3" in options.genotype:
					l2out = bar[2]+str(delimiter)
				elif "0" or "1" or "2" in options.genotype:
					l2out = bar[2]+str(delimiter)+bar[2]+str(delimiter)+bar[2]+str(delimiter)
				genomatrix_out.write(l2out)
		genomatrix_out.write("\n")
	
	## Output genotypes for each sample from VCF (begin at column 10)
	for vline in open(filtered_vcf, "r"):
		if not vline.strip().startswith("#"):
			bar = vline.rstrip().split("\t")
			if options.locinfo is True:
				genomatrix_out.write(bar[0]+"_"+bar[1]+str(delimiter))
			if options.refalt is True:
				genomatrix_out.write(bar[3]+str(delimiter)+bar[4]+str(delimiter))
			for sample in range(9, sample_total+9):
				vcfchunks = bar[sample].split(":")
				geno_out = recode_gl(genomatrix_out, vcfchunks[PL], delimiter)		# recode genotype likelihoods user choice
				genomatrix_out.write(geno_out+str(delimiter))
			genomatrix_out.write("\n")
	
	genomatrix_out.close()
	print "\n\n###The genotype likelihood matrix can be found in "+options.prefix+".genomatrix###\n\n"


#################################################
###    Creating nucleotide alignment fasta    ###
#################################################

## Create fasta alignment of nucleotides based on genotypes from each sample in VCF
def nucl_fasta(GT, GQ, filtered_vcf):
	counter = 0
	## Initalize output file
	nucl_out = open(options.prefix+".nucl.fasta", "w")
	
	## For each individual in sample sheet
	for line in open(options.sheet, "r"):
	    if not line.strip().startswith("#"):

			## Write out fasta header with sample ID and population ID
			nucl_out.write(">"+line.split("\t")[1]+"_"+line.split("\t")[2]+"_"+line.split("\t")[3])
			
			## For each line (locus) in VCF
			for vline in open(filtered_vcf, "r"):
				if not vline.strip().startswith("#"):
					bar = vline.rstrip().split("\t")
					
					## For each individual in VCF
					target = bar[counter + 9]
					vcfchunks = target.split(":")
					
					## Only write genotypes for loci with genotype quality greater than threshold
					if int(vcfchunks[GQ]) >= int(options.gq):
						
						if vcfchunks[GT] == "0/0":					# homozygous reference (4th column)
							nucl_out.write(str(bar[3]))
						elif vcfchunks[GT] == "1/1":
							nucl_out.write(str(bar[4]))				# homozygous alternative (5th column)
						else:
							nucl_out.write(str(get_amb(bar[3], bar[4])))	# heterozygous (use column 4/5 and subroutine to get ambiguity)
					
					## Else write missing data (?)
					else:
						nucl_out.write("?")
			nucl_out.write("\n")
			counter += 1
	
	nucl_out.close()
	print "\n\n###Nucleotide genotype alignment can be found in "+options.prefix+".nucl.fasta###\n\n"
	

#################################################
###      Creating trinary alignment fasta     ###
#################################################

## Create trinary fasta alignment based on genotypes from VCF... much the same as nucleotide function
def tri_fasta(GT, GQ, filtered_vcf):
	counter = 0
	## Initialize output file
	tri_out = open(options.prefix+".tri.fasta", "w")
	
	## For each individual in sample sheet
	for line in open(options.sheet, "r"):
	    if not line.strip().startswith("#"):
			
			## Write out fasta header with sample ID and population ID
			tri_out.write(">"+line.split()[1]+"_"+line.split()[2]+"_"+line.split()[3]+"\n")
			
			## for each line (locus) in VCF
			for vline in open(filtered_vcf, "r"):
				if not vline.strip().startswith("#"):
					bar = vline.rstrip().split("\t")
					
					## For each individual in VCF
					target = bar[counter + 9]
					vcfchunks = target.split(":")

					## Knly write genotypes for loci with genotype quality greater than threshold
					if int(vcfchunks[GQ]) >= int(options.gq):
						
						if vcfchunks[GT] == "0/0":				# homozygous reference = 0
							tri_out.write("0")
						elif vcfchunks[GT] == "1/1":			# homozygous alternative = 2
							tri_out.write("2")
						else:									# heterozygous = 1
							tri_out.write("1")
					
					## Else write missing data (?)
					else:
						tri_out.write("?")
			tri_out.write("\n")
			counter += 1
	
	tri_out.close()
	print "\n\n###Trinary genotype alignment can be found in "+options.prefix+".tri.fasta###\n\n"
	

#################################################
###      Subroutines for above functions      ###
#################################################	
					
## Convert PHRED genotype likelihoods to absolute genotypes (which account for uncertainty)
## Convert to likelihood (for each number alternative alleles): = 10 ^ PHRED/-10
## Standardize the likelihood (for each number alternative alleles): = likelihood/sum(all likelihoods)
## Multiple standardized likelihoods by number of alternative alles: = standardized likelihoods * # alternative alleles
## Sum to produce absolute genotype on 0 (homozygous reference) to 2 (homozygous alternative) scale
def recode_gl(outfile, genochunk, delimiter):
	bar = genochunk.split(",")
	p0 = float(10 ** (int(bar[0])/-10))
	p1 = float(10 ** (int(bar[1])/-10))
	p2 = float(10 ** (int(bar[2])/-10))
	psum = float(p0 + p1 + p2)
	g0 = float(p0/psum)
	g1 = float(p1/psum)
	g2 = float(p2/psum)
	gsum = float(float(g0*0) + float(g1*1) + float(g2*2))
	if options.genotype == "0":
		return bar[0]+delimiter+bar[1]+delimiter+bar[2]
	elif options.genotype == "1":
		return '{:.3f}'.format(p0)+delimiter+'{:.3f}'.format(p1)+delimiter+'{:.3f}'.format(p2)
	elif options.genotype == "2":
		return '{:.3f}'.format(g0)+delimiter+'{:.3f}'.format(g1)+delimiter+'{:.3f}'.format(g2)
	elif options.genotype == "3":
		return '{:.5f}'.format(gsum)
	else:
		print "\n\n***Specify the output genotype format for genotype matrix***\n\n"
		
## Determines which portion of the FORMAT column contains the genotype, PHRED genotype likelihood, and genotype quality
## Uses sample line from end of output VCF
## Splits by tabs to isolate FORMAT column (#9) and then splits by : to separate tags
## Returns the tag number of three values
def get_stat(filtered_VCF):
	os.system("tail -1 "+filtered_VCF+" > sample_VCF_line.txt")
	sample_line = open("sample_VCF_line.txt", "r").readline()
	chunks = sample_line.rstrip().split("\t")
	target = chunks[8]
	foo = target.split(":")
	GT = foo.index("GT")
	PL = foo.index("PL")
	GQ = foo.index("GQ")
	return GT, PL, GQ
	
## Determines the dimensions of the genotype matrix (individuals x loci)
## Uses a regular expression search of the VCFtools log
def get_vcf_dims():
	out = []
	if options.ind is True:
		file = options.prefix+".thin.log"
	else:
		file = options.prefix+".maf"+options.maf+".log"
	for line in open(file, "r"):
		if line.strip().startswith("After"):
			query = re.compile('kept (.*?) out')
			match = query.search(line)
			if match:
				element = match.group(1)
				out.append(element)
	return out

## Determine proper ambiguity code at a locus for heterozygous individuals
def get_amb(major, minor):
	if major == "A" and minor == "G":
		return "R"
	elif major == "G" and minor == "A":
		return "R"
	elif major == "C" and minor == "T":
		return "Y"
	elif major == "T" and minor == "C":
		return "Y"
	elif major == "G" and minor == "C":
		return "S"
	elif major == "C" and minor == "G":
		return "S"
	elif major == "A" and minor == "T":
		return "W"
	elif major == "T" and minor == "A":
		return "W"
	elif major == "G" and minor == "T":
		return "K"
	elif major == "T" and minor == "G":
		return "K"
	elif major == "A" and minor == "C":
		return "M"
	elif major == "C" and minor == "A":
		return "M"
	else:
		return "?"

def file_len(fname):
    count = 0
    with open(fname) as f:
        for line in f:
        	if not line.startswith("#"):
				count += 1
    return count


#################################################
###        		   Main Program               ###
#################################################

def main():
	## If previously filtered VCF is specified, use that, otherwise filter based on user input
	if options.filvcf == "":
		print "\n\n***Producing new VCF based on MAF and SNP independence settings***\n\n"
		vcf_filter()
		filtered_vcf = options.prefix+".maf"+options.maf+".recode.vcf"
	else:
		print "\n\n***Working from previously filtered VCF***\n\n"
		filtered_vcf = options.filvcf
	
	## Retrieve location of FORMAT flags so we can extract the values we want
	(GT, PL, GQ) = get_stat(filtered_vcf)
	
	## If user specified genotype likelihood output, give it to them
	if options.genotype is not "":
		print "\n\n***Creating a genotype likelihood matrix***\n\n"
		if options.delimit == "1":
			geno_matrix(PL, filtered_vcf, " ")
		elif options.delimit == "2":
			geno_matrix(PL, filtered_vcf, "\t")
		else:
			print "\n\n***Specify a delimiter for the genotype matrix!***\n\n"
	else:
		print "\n\n***Not creating a genotype likelihood matrix***\n\n"
	
	## If user specified nucleotide fasta output, give it to them
	if options.nucl is True:
		print "\n\n***Creating nucleotide SNP genotype alignment***\n\n"
		nucl_fasta(GT, GQ, filtered_vcf)
	else:
		print "\n\n***Not creating a nucleotide SNP genotype alignment***\n\n"
	
	## If user specified trinary fasta output, give it to them
	if options.tri is True:
		print "\n\n***Creating trinary SNP genotype alignment***\n\n"
		tri_fasta(GT, GQ, filtered_vcf)
	else:
		print "\n\n***Not creating a trinary SNP genotype alignment***\n\n"
	
	os.system("rm -f sample_VCF_line.txt")  # clean up
	
	print "\n\n###Command has finished###\n\n"


#################################################
###        	  Call Main Program               ###
#################################################

main()
        	
