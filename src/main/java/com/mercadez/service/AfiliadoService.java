package com.mercadez.service;

import com.mercadez.dto.*;
import com.mercadez.exception.*;
import com.mercadez.model.Afiliado;
import com.mercadez.repository.AfiliadoRepository;
import com.mercadez.security.JwtService;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AfiliadoService {

    private final AfiliadoRepository repo;
    private final PasswordEncoder    encoder;
    private final JwtService         jwt;

    public AfiliadoService(AfiliadoRepository repo, PasswordEncoder encoder, JwtService jwt) {
        this.repo    = repo;
        this.encoder = encoder;
        this.jwt     = jwt;
    }

    @Transactional
    public AfiliadoResponse cadastrar(CadastroAfiliadoRequest req) {
        if (repo.existsByEmail(req.getEmail())) {
            throw new NegocioException("Email já cadastrado.");
        }
        if (repo.existsByCnpj(req.getCnpj())) {
            throw new NegocioException("CNPJ já cadastrado.");
        }

        Afiliado a = Afiliado.builder()
                .nomeProprietario(req.getNome_proprietario())
                .email(req.getEmail().toLowerCase())
                .senha(encoder.encode(req.getSenha()))
                .cnpj(req.getCnpj())
                .endereco(req.getEndereco())
                .telefone(req.getTelefone())
                .mercado(req.getMercado())
                .categoria(req.getCategoria())
                .funcionarios(req.getFuncionarios())
                .pagamento(req.getPagamento())
                .build();

        return AfiliadoResponse.de(repo.save(a));
    }

    @Transactional(readOnly = true)
    public LoginResponse login(LoginRequest req) {
        Afiliado a = repo.findByEmail(req.getEmail().toLowerCase())
                .orElseThrow(CredenciaisInvalidasException::new);

        if (!encoder.matches(req.getSenha(), a.getSenha())) {
            throw new CredenciaisInvalidasException();
        }

        String token = jwt.gerarToken(a.getId(), a.getEmail(), "AFILIADO");
        return new LoginResponse(token, "Bearer", "AFILIADO", a.getId(), a.getNomeProprietario(), a.getEmail());
    }

    @Transactional(readOnly = true)
    public AfiliadoResponse buscarPorId(Long id) {
        return AfiliadoResponse.de(
                repo.findById(id).orElseThrow(() -> new NaoEncontradoException("Afiliado não encontrado."))
        );
    }
}
