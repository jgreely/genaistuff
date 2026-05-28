#!/usr/bin/env perl
#
# quick hack to strip out all server responses from an LM Studio chat,
# so the user prompts can be reused without the accumulated context.

use 5.020;
use strict;
use warnings;
use JSON;

open(my $In, $ARGV[0]);
my $json = join(' ', <$In>);
close($In);
my $conv = decode_json($json);

# remove token count
$conv->{tokenCount} = 0;

# rename
$conv->{name} = "SCRUBBED " . defined $conv->{name} ? $conv->{name} : "";

# remove all messages not from user.
my $out = [];
foreach my $msg (@{$conv->{messages}}) {
    push(@$out, $msg) if $msg->{versions}->[0]->{role} eq "user";
}
$conv->{messages} = $out;
print encode_json($conv);
