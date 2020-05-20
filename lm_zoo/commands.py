import sys

import click
import crayons
import dateutil
import h5py

import lm_zoo as Z
from lm_zoo.backends import BACKEND_DICT


zoo = Z.get_registry()


class ZooInstance(object):
    def __init__(self, requested_backend):
        self.requested_backend = requested_backend


@click.group(help="``lm-zoo`` provides black-box access to computing with state-of-the-art language models.")
@click.option("--backend", type=click.Choice(list(BACKEND_DICT.keys()), case_sensitive=False),
              help="Specify a backend (containerization platform) to run the specified model.")
@click.pass_context
def lm_zoo(ctx, backend):
    ctx.obj = ZooInstance(requested_backend=backend)


@lm_zoo.command()
@click.option("--short", is_flag=True, default=False,
              help="Output just a list of shortnames rather than a pretty list")
def list(short):
    """
    List language models available in the central repository.
    """
    show_props = [
        ("name", "Full name"),
        ("ref_url", "Reference URL"),
        ("maintainer", "Maintainer"),
    ]

    for _, model in Z.get_registry().items():
        if short:
            click.echo(model.name)
        else:
            click.echo(crayons.normal(model.name, bold=True))
            click.echo("\t{0} {1}".format(
                crayons.normal("Image URI: ", bold=True),
                model.image_uri))

            props = []
            for key, label in show_props:
                if hasattr(model, key):
                    props.append((label, getattr(model, key)))

            dt = dateutil.parser.isoparse(model.datetime)
            props.append(("Last updated", dt.strftime("%Y-%m-%d")))
            props.append(("Size", "%.02fGB" % (model.size / 1024 / 1024 / 1024)))

            for label, value in props:
                click.echo("\t" + crayons.normal(label + ": ", bold=True)
                            + value)

def read_lines(fstream):
    return [line.strip() for line in fstream]


@lm_zoo.command()
@click.argument("model", metavar="MODEL")
@click.argument("in_file", type=click.File("r"), metavar="FILE")
@click.pass_obj
def tokenize(obj, model, in_file):
    """
    Tokenize natural-language text according to a model's preprocessing
    standards.

    FILE should be a raw natural language text file with one sentence per line.

    This command returns a text file with one tokenized sentence per line, with
    tokens separated by single spaces. For each sentence, there is a one-to-one
    mapping between the tokens output by this command and the tokens used by
    the ``get-surprisals`` command.
    """
    model = zoo[model]
    sentences = read_lines(in_file)
    sentences = Z.tokenize(model, sentences,
                           backend=obj.requested_backend)
    print("\n".join(" ".join(sentence) for sentence in sentences))


@lm_zoo.command()
@click.argument("model", metavar="MODEL")
@click.argument("in_file", type=click.File("r"), metavar="FILE")
@click.pass_obj
def get_surprisals(obj, model, in_file):
    """
    Get word-level surprisals from a language model for the given natural
    language text. Tab-separated results will be sent to standard output,
    following the format::

      sentence_id	token_id	token	surprisal
      1			1		This	0.000
      1			2		is	1.000
      1			3		a	1.000
      1			4		<unk>	0.500
      1			5		line	1.000
      1			6		.	0.250
      1			7		<eos>	0.100

    The surprisal of a token :math:`w_i` is the negative logarithm of that
    token's probability under a language model's predictive distribution:

    .. math::
        S(w_i) = -\log_2 p(w_i \mid w_1, w_2, \ldots, w_{i-1})

    Note that surprisals are computed on the level of **tokens**, not words.
    Models that insert extra tokens (e.g., an end-of-sentence token as above)
    or which tokenize on the sub-word level (e.g. GPT2) will not have a
    one-to-one mapping between rows of surprisal output from this command and
    words.

    There is guaranteed to be a one-to-one mapping, however, between the rows
    of this file and the tokens produced by ``lm-zoo tokenize``.
    """
    model = zoo[model]
    sentences = read_lines(in_file)
    ret = Z.get_surprisals(model, sentences, backend=obj.requested_backend)
    ret.to_csv(sys.stdout, sep="\t")


@lm_zoo.command()
@click.argument("model", metavar="MODEL")
@click.argument("in_file", type=click.File("r"), metavar="FILE")
@click.pass_obj
def unkify(obj, model, in_file):
    """
    Detect unknown words for a language model for the given natural language
    text.

    FILE should be a raw natural language text file with one sentence per line.

    This command returns a text file with one sentence per line, where each
    sentence is represented as a sequence of ``0`` and ``1`` values. These
    values correspond one-to-one with the model's tokenization of the sentence
    (as returned by ``lm-zoo tokenize``). The value ``0`` indicates that the
    corresponding token is in the model's vocabulary; the value ``1`` indicates
    that the corresponding token is an unknown word for the model.
    """
    model = zoo[model]
    sentences = read_lines(in_file)
    masks = Z.unkify(model, sentences, backend=obj.requested_backend)
    print("\n".join(" ".join(map(str, masks_i)) for masks_i in masks))


@lm_zoo.command()
@click.argument("model", metavar="MODEL")
@click.argument("in_file", type=click.File("r"), metavar="INFILE")
@click.argument("out_file", type=click.File("wb"), metavar="OUTFILE")
@click.pass_obj
def get_predictions(obj, model, in_file, out_file):
    """
    Compute token-level predictive distributions from a language model for the
    given natural language sentences.

    INFILE should be a raw natural language text file with one sentence per line.

    This command writes a HDF5 file to the given OUTFILE, with the following
    structure::

        /sentence/<i>/predictions: N_tokens_i * N_vocabulary array of
            log-probabilities (rows are log-probability distributions)
        /sentence/<i>/tokens: sequence of integer token IDs corresponding to
            indices in ``/vocabulary``
        /vocabulary: byte-encoded string array of vocabulary items (decode with
            ``numpy.char.decode(vocabulary, "utf-8")``)
    """
    model = zoo[model]
    sentences = read_lines(in_file)
    result = Z.get_predictions(model, sentences, backend=obj.requested_backend)

    with h5py.File(out_file.name, "w") as out:
        result.copy("sentence", out)
        result.copy("vocabulary", out)
