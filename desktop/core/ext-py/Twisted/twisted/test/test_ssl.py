# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for twisted SSL support.
"""

from twisted.trial import unittest
from twisted.internet import protocol, reactor, interfaces, defer
from twisted.protocols import basic
from twisted.python import util
from twisted.python.runtime import platform
from twisted.test.test_tcp import WriteDataTestCase, ProperlyCloseFilesMixin

import os, errno

try:
    from OpenSSL import SSL, crypto
    from twisted.internet import ssl
    from twisted.test.ssl_helpers import ClientTLSContext
except ImportError:
    def _noSSL():
        # ugh, make pyflakes happy.
        global SSL
        global ssl
        SSL = ssl = None
    _noSSL()

certPath = util.sibpath(__file__, "server.pem")



class UnintelligentProtocol(basic.LineReceiver):
    """
    @ivar deferred: a deferred that will fire at connection lost.
    @type deferred: L{defer.Deferred}

    @cvar pretext: text sent before TLS is set up.
    @type pretext: C{str}

    @cvar posttext: text sent after TLS is set up.
    @type posttext: C{str}
    """
    pretext = [
        "first line",
        "last thing before tls starts",
        "STARTTLS"]

    posttext = [
        "first thing after tls started",
        "last thing ever"]

    def __init__(self):
        self.deferred = defer.Deferred()


    def connectionMade(self):
        for l in self.pretext:
            self.sendLine(l)


    def lineReceived(self, line):
        if line == "READY":
            self.transport.startTLS(ClientTLSContext(), self.factory.client)
            for l in self.posttext:
                self.sendLine(l)
            self.transport.loseConnection()


    def connectionLost(self, reason):
        self.deferred.callback(None)



class LineCollector(basic.LineReceiver):
    """
    @ivar deferred: a deferred that will fire at connection lost.
    @type deferred: L{defer.Deferred}

    @ivar doTLS: whether the protocol is initiate TLS or not.
    @type doTLS: C{bool}

    @ivar fillBuffer: if set to True, it will send lots of data once
        C{STARTTLS} is received.
    @type fillBuffer: C{bool}
    """

    def __init__(self, doTLS, fillBuffer=False):
        self.doTLS = doTLS
        self.fillBuffer = fillBuffer
        self.deferred = defer.Deferred()


    def connectionMade(self):
        self.factory.rawdata = ''
        self.factory.lines = []


    def lineReceived(self, line):
        self.factory.lines.append(line)
        if line == 'STARTTLS':
            if self.fillBuffer:
                for x in range(500):
                    self.sendLine('X' * 1000)
            self.sendLine('READY')
            if self.doTLS:
                ctx = ServerTLSContext(
                    privateKeyFileName=certPath,
                    certificateFileName=certPath,
                )
                self.transport.startTLS(ctx, self.factory.server)
            else:
                self.setRawMode()


    def rawDataReceived(self, data):
        self.factory.rawdata += data
        self.transport.loseConnection()


    def connectionLost(self, reason):
        self.deferred.callback(None)



class SingleLineServerProtocol(protocol.Protocol):
    """
    A protocol that sends a single line of data at C{connectionMade}.
    """

    def connectionMade(self):
        self.transport.write("+OK <some crap>\r\n")
        self.transport.getPeerCertificate()



class RecordingClientProtocol(protocol.Protocol):
    """
    @ivar deferred: a deferred that will fire with first received content.
    @type deferred: L{defer.Deferred}
    """

    def __init__(self):
        self.deferred = defer.Deferred()


    def connectionMade(self):
        self.transport.getPeerCertificate()


    def dataReceived(self, data):
        self.deferred.callback(data)



class ImmediatelyDisconnectingProtocol(protocol.Protocol):
    """
    A protocol that disconnect immediately on connection. It fires the
    C{connectionDisconnected} deferred of its factory on connetion lost.
    """

    def connectionMade(self):
        self.transport.loseConnection()


    def connectionLost(self, reason):
        self.factory.connectionDisconnected.callback(None)



def generateCertificateObjects(organization, organizationalUnit):
    """
    Create a certificate for given C{organization} and C{organizationalUnit}.

    @return: a tuple of (key, request, certificate) objects.
    """
    pkey = crypto.PKey()
    pkey.generate_key(crypto.TYPE_RSA, 512)
    req = crypto.X509Req()
    subject = req.get_subject()
    subject.O = organization
    subject.OU = organizationalUnit
    req.set_pubkey(pkey)
    req.sign(pkey, "md5")

    # Here comes the actual certificate
    cert = crypto.X509()
    cert.set_serial_number(1)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(60) # Testing certificates need not be long lived
    cert.set_issuer(req.get_subject())
    cert.set_subject(req.get_subject())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(pkey, "md5")

    return pkey, req, cert



def generateCertificateFiles(basename, organization, organizationalUnit):
    """
    Create certificate files key, req and cert prefixed by C{basename} for
    given C{organization} and C{organizationalUnit}.
    """
    pkey, req, cert = generateCertificateObjects(organization, organizationalUnit)

    for ext, obj, dumpFunc in [
        ('key', pkey, crypto.dump_privatekey),
        ('req', req, crypto.dump_certificate_request),
        ('cert', cert, crypto.dump_certificate)]:
        fName = os.extsep.join((basename, ext))
        fObj = file(fName, 'w')
        fObj.write(dumpFunc(crypto.FILETYPE_PEM, obj))
        fObj.close()



class ContextGeneratingMixin:
    """
    Offer methods to create L{ssl.DefaultOpenSSLContextFactory} for both client
    and server.

    @ivar clientBase: prefix of client certificate files.
    @type clientBase: C{str}

    @ivar serverBase: prefix of server certificate files.
    @type serverBase: C{str}

    @ivar clientCtxFactory: a generated context factory to be used in
        C{reactor.connectSSL}.
    @type clientCtxFactory: L{ssl.DefaultOpenSSLContextFactory}

    @ivar serverCtxFactory: a generated context factory to be used in
        C{reactor.listenSSL}.
    @type serverCtxFactory: L{ssl.DefaultOpenSSLContextFactory}
    """

    def makeContextFactory(self, org, orgUnit, *args, **kwArgs):
        base = self.mktemp()
        generateCertificateFiles(base, org, orgUnit)
        serverCtxFactory = ssl.DefaultOpenSSLContextFactory(
            os.extsep.join((base, 'key')),
            os.extsep.join((base, 'cert')),
            *args, **kwArgs)

        return base, serverCtxFactory


    def setupServerAndClient(self, clientArgs, clientKwArgs, serverArgs,
                             serverKwArgs):
        self.clientBase, self.clientCtxFactory = self.makeContextFactory(
            *clientArgs, **clientKwArgs)
        self.serverBase, self.serverCtxFactory = self.makeContextFactory(
            *serverArgs, **serverKwArgs)



if SSL is not None:
    class ServerTLSContext(ssl.DefaultOpenSSLContextFactory):
        """
        A context factory with a default method set to L{SSL.TLSv1_METHOD}.
        """
        isClient = False

        def __init__(self, *args, **kw):
            kw['sslmethod'] = SSL.TLSv1_METHOD
            ssl.DefaultOpenSSLContextFactory.__init__(self, *args, **kw)



class StolenTCPTestCase(ProperlyCloseFilesMixin, WriteDataTestCase):
    """
    For SSL transports, test many of the same things which are tested for
    TCP transports.
    """

    def createServer(self, address, portNumber, factory):
        """
        Create an SSL server with a certificate using L{IReactorSSL.listenSSL}.
        """
        cert = ssl.PrivateCertificate.loadPEM(file(certPath).read())
        contextFactory = cert.options()
        return reactor.listenSSL(
            portNumber, factory, contextFactory, interface=address)


    def connectClient(self, address, portNumber, clientCreator):
        """
        Create an SSL client using L{IReactorSSL.connectSSL}.
        """
        contextFactory = ssl.CertificateOptions()
        return clientCreator.connectSSL(address, portNumber, contextFactory)


    def getHandleExceptionType(self):
        """
        Return L{SSL.Error} as the expected error type which will be raised by
        a write to the L{OpenSSL.SSL.Connection} object after it has been
        closed.
        """
        return SSL.Error


    def getHandleErrorCode(self):
        """
        Return the argument L{SSL.Error} will be constructed with for this
        case.  This is basically just a random OpenSSL implementation detail.
        It would be better if this test worked in a way which did not require
        this.
        """
        # Windows 2000 SP 4 and Windows XP SP 2 give back WSAENOTSOCK for
        # SSL.Connection.write for some reason.
        if platform.getType() == 'win32':
            return errno.WSAENOTSOCK
        # This is terribly implementation-specific.
        return [('SSL routines', 'SSL_write', 'protocol is shutdown')]



class TLSTestCase(unittest.TestCase):
    """
    Tests for startTLS support.

    @ivar fillBuffer: forwarded to L{LineCollector.fillBuffer}
    @type fillBuffer: C{bool}
    """
    fillBuffer = False

    clientProto = None
    serverProto = None


    def tearDown(self):
        if self.clientProto.transport is not None:
            self.clientProto.transport.loseConnection()
        if self.serverProto.transport is not None:
            self.serverProto.transport.loseConnection()


    def _runTest(self, clientProto, serverProto, clientIsServer=False):
        """
        Helper method to run TLS tests.

        @param clientProto: protocol instance attached to the client
            connection.
        @param serverProto: protocol instance attached to the server
            connection.
        @param clientIsServer: flag indicated if client should initiate
            startTLS instead of server.

        @return: a L{defer.Deferred} that will fire when both connections are
            lost.
        """
        self.clientProto = clientProto
        cf = self.clientFactory = protocol.ClientFactory()
        cf.protocol = lambda: clientProto
        if clientIsServer:
            cf.server = False
        else:
            cf.client = True

        self.serverProto = serverProto
        sf = self.serverFactory = protocol.ServerFactory()
        sf.protocol = lambda: serverProto
        if clientIsServer:
            sf.client = False
        else:
            sf.server = True

        port = reactor.listenTCP(0, sf, interface="127.0.0.1")
        self.addCleanup(port.stopListening)

        reactor.connectTCP('127.0.0.1', port.getHost().port, cf)

        return defer.gatherResults([clientProto.deferred, serverProto.deferred])


    def test_TLS(self):
        """
        Test for server and client startTLS: client should received data both
        before and after the startTLS.
        """
        def check(ignore):
            self.assertEquals(
                self.serverFactory.lines,
                UnintelligentProtocol.pretext + UnintelligentProtocol.posttext
            )
        d = self._runTest(UnintelligentProtocol(),
                          LineCollector(True, self.fillBuffer))
        return d.addCallback(check)


    def test_unTLS(self):
        """
        Test for server startTLS not followed by a startTLS in client: the data
        received after server startTLS should be received as raw.
        """
        def check(ignored):
            self.assertEquals(
                self.serverFactory.lines,
                UnintelligentProtocol.pretext
            )
            self.failUnless(self.serverFactory.rawdata,
                            "No encrypted bytes received")
        d = self._runTest(UnintelligentProtocol(),
                          LineCollector(False, self.fillBuffer))
        return d.addCallback(check)


    def test_backwardsTLS(self):
        """
        Test startTLS first initiated by client.
        """
        def check(ignored):
            self.assertEquals(
                self.clientFactory.lines,
                UnintelligentProtocol.pretext + UnintelligentProtocol.posttext
            )
        d = self._runTest(LineCollector(True, self.fillBuffer),
                          UnintelligentProtocol(), True)
        return d.addCallback(check)



class SpammyTLSTestCase(TLSTestCase):
    """
    Test TLS features with bytes sitting in the out buffer.
    """
    fillBuffer = True



class BufferingTestCase(unittest.TestCase):
    serverProto = None
    clientProto = None


    def tearDown(self):
        if self.serverProto.transport is not None:
            self.serverProto.transport.loseConnection()
        if self.clientProto.transport is not None:
            self.clientProto.transport.loseConnection()


    def test_openSSLBuffering(self):
        serverProto = self.serverProto = SingleLineServerProtocol()
        clientProto = self.clientProto = RecordingClientProtocol()

        server = protocol.ServerFactory()
        client = self.client = protocol.ClientFactory()

        server.protocol = lambda: serverProto
        client.protocol = lambda: clientProto

        sCTX = ssl.DefaultOpenSSLContextFactory(certPath, certPath)
        cCTX = ssl.ClientContextFactory()

        port = reactor.listenSSL(0, server, sCTX, interface='127.0.0.1')
        self.addCleanup(port.stopListening)

        reactor.connectSSL('127.0.0.1', port.getHost().port, client, cCTX)

        return clientProto.deferred.addCallback(
            self.assertEquals, "+OK <some crap>\r\n")



class ConnectionLostTestCase(unittest.TestCase, ContextGeneratingMixin):

    def testImmediateDisconnect(self):
        org = "twisted.test.test_ssl"
        self.setupServerAndClient(
            (org, org + ", client"), {},
            (org, org + ", server"), {})

        # Set up a server, connect to it with a client, which should work since our verifiers
        # allow anything, then disconnect.
        serverProtocolFactory = protocol.ServerFactory()
        serverProtocolFactory.protocol = protocol.Protocol
        self.serverPort = serverPort = reactor.listenSSL(0,
            serverProtocolFactory, self.serverCtxFactory)

        clientProtocolFactory = protocol.ClientFactory()
        clientProtocolFactory.protocol = ImmediatelyDisconnectingProtocol
        clientProtocolFactory.connectionDisconnected = defer.Deferred()
        clientConnector = reactor.connectSSL('127.0.0.1',
            serverPort.getHost().port, clientProtocolFactory, self.clientCtxFactory)

        return clientProtocolFactory.connectionDisconnected.addCallback(
            lambda ignoredResult: self.serverPort.stopListening())


    def testFailedVerify(self):
        org = "twisted.test.test_ssl"
        self.setupServerAndClient(
            (org, org + ", client"), {},
            (org, org + ", server"), {})

        def verify(*a):
            return False
        self.clientCtxFactory.getContext().set_verify(SSL.VERIFY_PEER, verify)

        serverConnLost = defer.Deferred()
        serverProtocol = protocol.Protocol()
        serverProtocol.connectionLost = serverConnLost.callback
        serverProtocolFactory = protocol.ServerFactory()
        serverProtocolFactory.protocol = lambda: serverProtocol
        self.serverPort = serverPort = reactor.listenSSL(0,
            serverProtocolFactory, self.serverCtxFactory)

        clientConnLost = defer.Deferred()
        clientProtocol = protocol.Protocol()
        clientProtocol.connectionLost = clientConnLost.callback
        clientProtocolFactory = protocol.ClientFactory()
        clientProtocolFactory.protocol = lambda: clientProtocol
        clientConnector = reactor.connectSSL('127.0.0.1',
            serverPort.getHost().port, clientProtocolFactory, self.clientCtxFactory)

        dl = defer.DeferredList([serverConnLost, clientConnLost], consumeErrors=True)
        return dl.addCallback(self._cbLostConns)


    def _cbLostConns(self, results):
        (sSuccess, sResult), (cSuccess, cResult) = results

        self.failIf(sSuccess)
        self.failIf(cSuccess)

        acceptableErrors = [SSL.Error]

        # Rather than getting a verification failure on Windows, we are getting
        # a connection failure.  Without something like sslverify proxying
        # in-between we can't fix up the platform's errors, so let's just
        # specifically say it is only OK in this one case to keep the tests
        # passing.  Normally we'd like to be as strict as possible here, so
        # we're not going to allow this to report errors incorrectly on any
        # other platforms.

        if platform.isWindows():
            from twisted.internet.error import ConnectionLost
            acceptableErrors.append(ConnectionLost)

        sResult.trap(*acceptableErrors)
        cResult.trap(*acceptableErrors)

        return self.serverPort.stopListening()



if interfaces.IReactorSSL(reactor, None) is None:
    for tCase in [StolenTCPTestCase, TLSTestCase, SpammyTLSTestCase,
                  BufferingTestCase, ConnectionLostTestCase]:
        tCase.skip = "Reactor does not support SSL, cannot run SSL tests"

# Otherwise trial will run this test here
del WriteDataTestCase
